from __future__ import annotations

import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def _get_enabled_scrapers(config: Config) -> list:
    import os

    scrapers = []

    jsearch_key = os.getenv("JSEARCH_API_KEY", "")
    if jsearch_key and config.scraper.jsearch_enabled:
        from nj.scrapers.jsearch import JSearchScraper

        scrapers.append(JSearchScraper(api_key=jsearch_key, visa_config=config.visa))

    li_at = os.getenv("LINKEDIN_LI_AT", "")
    if li_at and config.scraper.linkedin_enabled:
        from nj.scrapers.linkedin import LinkedInScraper

        scrapers.append(
            LinkedInScraper(session_cookie=li_at, visa_config=config.visa, headless=True)
        )

    adzuna_id = os.getenv("ADZUNA_APP_ID", config.scraper.adzuna_app_id)
    adzuna_key = os.getenv("ADZUNA_APP_KEY", config.scraper.adzuna_app_key)
    if adzuna_id and config.scraper.adzuna_enabled:
        from nj.scrapers.indeed import AdzunaScraper

        scrapers.append(
            AdzunaScraper(
                app_id=adzuna_id,
                app_key=adzuna_key,
                visa_config=config.visa,
                country=config.scraper.adzuna_country,
            )
        )

    if config.scraper.remoteok_enabled:
        from nj.scrapers.remoteok import RemoteOKScraper

        scrapers.append(RemoteOKScraper(visa_config=config.visa))

    if config.scraper.weworkremotely_enabled:
        from nj.scrapers.weworkremotely import WeWorkRemotelyScraper

        scrapers.append(WeWorkRemotelyScraper(visa_config=config.visa))

    if config.scraper.arbeitnow_enabled:
        from nj.scrapers.arbeitnow import ArbeitnowScraper

        scrapers.append(ArbeitnowScraper(visa_config=config.visa))

    usajobs_key = os.getenv("USAJOBS_API_KEY", "")
    usajobs_agent = os.getenv("USAJOBS_USER_AGENT", "")
    if usajobs_key and usajobs_agent and config.scraper.usajobs_enabled:
        from nj.scrapers.usajobs import USAJobsScraper

        scrapers.append(
            USAJobsScraper(
                api_key=usajobs_key,
                user_agent=usajobs_agent,
                visa_config=config.visa,
            )
        )

    if not scrapers:
        from nj.scrapers.remoteok import RemoteOKScraper

        scrapers.append(RemoteOKScraper(visa_config=config.visa))

    return scrapers


def run_search(
    config: Config,
    db_path: str = "data/nj.db",
    dry_run: bool = False,
) -> None:
    import asyncio

    from dotenv import load_dotenv

    from nj.db.engine import init_db
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo
    from nj.providers.registry import get_provider
    from nj.scoring.scorer import score_job
    from nj.scoring.visa_filter import VisaFilter
    from nj.utils.dedup import JobDeduplicator

    load_dotenv()
    scrapers = _get_enabled_scrapers(config)
    logger.info("scrapers_active", scrapers=[s.name() for s in scrapers])

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print(
            "[red]cv/cv_base.json not found.[/red] " "Run [bold]nj init[/bold] first."
        )
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    init_db(db_path)
    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)
    dedup = JobDeduplicator(job_repo)
    provider = get_provider(config.llm)
    visa_filter = VisaFilter(config.visa)

    from nj.utils.logger import is_verbose

    import asyncio
    import inspect
    import time

    async def _scrape_one(scraper) -> tuple[str, list]:
        try:
            if inspect.iscoroutinefunction(scraper.scrape):
                jobs = await scraper.scrape(
                    config.search.roles,
                    config.search.primary_region,
                )
            else:
                jobs = await asyncio.to_thread(
                    scraper.scrape,
                    config.search.roles,
                    config.search.primary_region,
                )
            logger.info("scraper_done", scraper=scraper.name(), count=len(jobs))
            return scraper.name(), jobs
        except Exception as e:
            logger.warning("scraper_failed", scraper=scraper.name(), error=str(e))
            return scraper.name(), []

    async def _scrape_all() -> dict[str, list]:
        results = await asyncio.gather(
            *[_scrape_one(s) for s in scrapers], return_exceptions=True
        )
        output = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning("scraper_gather_failed", error=str(result))
                continue
            name, jobs = result
            output[name] = jobs
        return output

    t_start = time.monotonic()
    scraper_results = asyncio.run(_scrape_all())
    t_elapsed = round(time.monotonic() - t_start, 1)

    all_raw_jobs: list = []
    counts: dict[str, int] = {}
    for name, jobs in scraper_results.items():
        counts[name] = len(jobs)
        all_raw_jobs.extend(jobs)

    new_jobs = dedup.filter_new(all_raw_jobs)
    for job in new_jobs:
        job_repo.save_job(job)
    all_jobs = list(new_jobs)

    if not is_verbose():
        total = sum(counts.values())
        sources = " · ".join(
            f"{name}={count}" for name, count in counts.items() if count > 0
        )
        console.print(
            f"\n[green]✓[/green] Scraped [bold]{total}[/bold] jobs in "
            f"[cyan]{t_elapsed}s[/cyan]  "
            f"[dim]({len(all_raw_jobs) - len(new_jobs)} dupes skipped)[/dim]"
        )
        if sources:
            console.print(f"[dim]Sources: {sources}[/dim]")

    from nj.scoring.ghost_filter import GhostJobFilter

    ghost_filter = GhostJobFilter(enabled=True, max_age_days=45)
    all_jobs, ghost_jobs = ghost_filter.filter_jobs(all_jobs)

    if ghost_jobs and not is_verbose():
        console.print(
            f"[dim]Ghost filter: {len(ghost_jobs)} jobs removed "
            f"({len(all_jobs)} remaining)[/dim]"
        )
    elif ghost_jobs and is_verbose():
        console.print(f"[dim]Ghost filter removed {len(ghost_jobs)} jobs:[/dim]")
        for job, result in ghost_jobs[:5]:
            console.print(
                f"  [dim]✗ {job.title[:30]} @ {job.company[:20]} — {result.reason}[/dim]"
            )

    if not all_jobs:
        console.print("[yellow]No new jobs found.[/yellow]")
        return

    console.print(
        f"\n[bold]{len(all_jobs)} new jobs found.[/bold] " f"Scoring now...\n"
    )

    from nj.intel.enrichment import JobEnrichment
    from nj.db.repos.enrichment_repo import EnrichmentRepo

    enricher = JobEnrichment(db_path=db_path)
    enrichment_repo = EnrichmentRepo(db_path=db_path)

    if not is_verbose():
        console.print("[dim]Enriching jobs with intel...[/dim]")
    enrichments = enricher.enrich_batch(all_jobs, cv_base)
    for job_id, enrichment in enrichments.items():
        enrichment_repo.save_enrichment(job_id, enrichment)

    from asyncio import Semaphore
    from nj.models.job import JobStatus

    jobs_to_score = [j for j in all_jobs if not visa_filter.should_skip(j)]
    blocked = len(all_jobs) - len(jobs_to_score)

    if dry_run:
        _display_search_results([], blocked, dry_run, enrichments)
        return

    async def _score_all_jobs(
        jobs: list,
        semaphore: Semaphore,
    ) -> list:
        async def _score_one(job):
            async with semaphore:
                try:
                    return job, await score_job(
                        job=job,
                        cv_base=cv_base,
                        config=config,
                        provider=provider,
                        repo=score_repo,
                    )
                except Exception as e:
                    logger.warning("score_failed", job_id=job.id, error=str(e))
                    return None

        results = await asyncio.gather(*[_score_one(j) for j in jobs])
        return [r for r in results if r is not None]

    sem = Semaphore(5)
    t_score_start = time.monotonic()
    score_pairs = asyncio.run(_score_all_jobs(jobs_to_score, sem))
    t_score_elapsed = round(time.monotonic() - t_score_start, 1)

    scored = []
    for job, result in score_pairs:
        job.status = JobStatus.PENDING_REVIEW
        job_repo.update_job_status(job.id, JobStatus.PENDING_REVIEW)
        scored.append((job, result))

    if not is_verbose():
        console.print(
            f"[green]✓[/green] Scored [bold]{len(scored)}[/bold] jobs in "
            f"[cyan]{t_score_elapsed}s[/cyan]"
        )

    _display_search_results(scored, blocked, dry_run, enrichments)


def _display_search_results(
    scored: list,
    blocked: int,
    dry_run: bool,
    enrichments: dict | None = None,
) -> None:
    if not scored:
        console.print(
            f"[yellow]No scoreable jobs.[/yellow] "
            f"({blocked} blocked by visa filter)"
        )
        return

    enrichments = enrichments or {}

    table = Table(
        title="Search results",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Score", width=7, justify="center")
    table.add_column("Sponsor%", width=9, justify="center")
    table.add_column("Salary est", width=12, justify="right")
    table.add_column("Visa", width=11)
    table.add_column("Company", width=20)
    table.add_column("Role", width=28)

    for job, result in sorted(scored, key=lambda x: x[1].total_score, reverse=True):
        score = result.total_score
        color = "green" if score >= 75 else "yellow" if score >= 60 else "red"

        enrichment = enrichments.get(job.id, {})
        sponsor = enrichment.get("sponsorship") or {}
        salary_data = enrichment.get("salary") or {}

        prob = sponsor.get("probability")
        sponsor_str = f"{prob:.0%}" if prob is not None else "—"
        sponsor_color = (
            "green"
            if prob and prob >= 0.7
            else "yellow"
            if prob and prob >= 0.45
            else "dim"
        )

        salary_pred = salary_data.get("predicted_salary")
        salary_str = f"${salary_pred // 1000}k" if salary_pred else "—"

        table.add_row(
            f"[{color}]{score}[/{color}]",
            f"[{sponsor_color}]{sponsor_str}[/{sponsor_color}]",
            salary_str,
            job.visa_label.value,
            job.company[:20],
            job.title[:28],
        )

    console.print(table)
    threshold = 62
    above = sum(1 for _, r in scored if r.total_score >= threshold)
    console.print(
        f"\n[bold]{above}[/bold] jobs above threshold ({threshold}). "
        f"[bold]{blocked}[/bold] blocked by visa filter.\n"
        f"Run [bold]nj review[/bold] to approve jobs for applying."
    )
    if dry_run:
        console.print("[dim]Dry run — no scores saved.[/dim]")
