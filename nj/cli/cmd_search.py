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

    all_jobs = []
    counts: dict[str, int] = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping jobs...", total=None)
        all_raw_jobs = []
        for scraper in scrapers:
            try:
                progress.update(task, description=f"Scraping {scraper.name()}...")
                fetched = scraper.scrape(
                    roles=config.search.roles,
                    location=config.search.primary_region,
                )
                counts[scraper.name()] = len(fetched)
                all_raw_jobs.extend(fetched)
                logger.info("scraper_done", scraper=scraper.name(), count=len(fetched))
            except Exception as e:
                counts[scraper.name()] = 0
                logger.warning("scraper_failed", scraper=scraper.name(), error=str(e))
        new_jobs = dedup.filter_new(all_raw_jobs)
        for job in new_jobs:
            job_repo.save_job(job)
        all_jobs.extend(new_jobs)
        progress.update(
            task,
            description=f"Scraped {len(new_jobs)} new jobs from {len(scrapers)} sources",
        )

    if not is_verbose():
        console.print(
            f"\n[green]✓[/green] Scraped [bold]{len(all_raw_jobs)}[/bold] jobs  "
            f"[dim]({len(all_raw_jobs) - len(new_jobs)} duplicates skipped)[/dim]"
        )
        console.print(
            "[dim]Sources: "
            + " · ".join(
                f"{s.name()}={counts.get(s.name(), 0)}" for s in scrapers
            )
            + "[/dim]"
        )

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

    scored = []
    blocked = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scoring...", total=len(all_jobs))
        for job in all_jobs:
            if visa_filter.should_skip(job):
                blocked += 1
                progress.advance(task)
                continue
            if dry_run:
                progress.advance(task)
                continue
            result = asyncio.run(score_job(job, cv_base, config, provider, score_repo))
            from nj.models.job import JobStatus

            job.status = JobStatus.PENDING_REVIEW
            job_repo.update_job_status(job.id, JobStatus.PENDING_REVIEW)
            scored.append((job, result))
            progress.advance(task)

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
