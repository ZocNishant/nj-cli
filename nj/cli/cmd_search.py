from __future__ import annotations

import json
import time
from pathlib import Path

from rich import box
from rich.console import Console
from rich.live import Live
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

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


SENIORITY_FILTERS = {
    "junior": {
        "include": [
            "junior",
            "entry",
            "associate",
            "new grad",
            "graduate",
            "intern",
            "0-2",
            "early career",
        ],
        "exclude": [
            "senior",
            "staff",
            "principal",
            "director",
            "vp",
            "head of",
            "manager",
            "lead",
        ],
    },
    "mid": {
        "include": [],
        "exclude": [
            "junior",
            "entry level",
            "director",
            "vp ",
            "chief",
            "head of",
            "c-level",
        ],
    },
    "senior": {
        "include": ["senior", "lead", "sr.", "sr ", "experienced", "5+", "6+", "7+"],
        "exclude": ["junior", "entry", "intern", "director", "vp", "chief"],
    },
    "staff": {
        "include": ["staff", "principal", "architect", "distinguished", "fellow"],
        "exclude": ["junior", "entry", "associate"],
    },
}


def _get_level_indicator(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["junior", "entry", "intern", "werkstudent", "praktikum"]):
        return "[dim]jr[/dim] "
    if any(x in t for x in ["senior", "sr.", " sr ", "lead"]):
        return "[yellow]sr[/yellow] "
    if any(x in t for x in ["staff", "principal", "architect"]):
        return "[cyan]st[/cyan] "
    if any(x in t for x in ["director", "vp ", "head of", "chief"]):
        return "[red]dir[/red] "
    return ""


def _is_likely_english(job) -> bool:
    german_signals = [
        "gmbh",
        "m/w/d",
        "w/m/d",
        "(m/w",
        "werkstudent",
        "praktikum",
        "vollzeit",
        "teilzeit",
        "entwickler",
        "(mensch)",
        "steuerberat",
    ]
    text = (job.title + " " + job.company).lower()
    return not any(sig in text for sig in german_signals)


def _apply_seniority_filter(jobs: list, level: str) -> tuple[list, int]:
    if level not in SENIORITY_FILTERS:
        return jobs, 0
    rules = SENIORITY_FILTERS[level]
    exclude = rules["exclude"]
    filtered = []
    removed = 0
    for job in jobs:
        text = job.title.lower() + " " + job.description.lower()[:500]
        if any(ex in text for ex in exclude):
            removed += 1
            continue
        filtered.append(job)
    return filtered, removed


def run_search(
    config: Config,
    db_path: str = "data/nj.db",
    dry_run: bool = False,
    level: str | None = None,
    limit: int = 50,
    all_langs: bool = False,
    visa_mode: str = "any",
) -> None:
    import asyncio

    from nj.db.engine import init_db
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo
    from nj.providers.registry import get_provider
    from nj.scoring.scorer import score_job
    from nj.scoring.visa_filter import VisaFilter
    from nj.utils.dedup import JobDeduplicator

    scrapers = _get_enabled_scrapers(config)
    logger.info("scrapers_active", scrapers=[s.name() for s in scrapers])

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print("[red]cv/cv_base.json not found.[/red] Run [bold]nj init[/bold] first.")
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    init_db(db_path)
    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)
    dedup = JobDeduplicator(job_repo)
    provider = get_provider(config.llm, task="scoring")
    visa_filter = VisaFilter(config.visa)

    import inspect

    from nj.utils.logger import is_verbose

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
        results = await asyncio.gather(*[_scrape_one(s) for s in scrapers], return_exceptions=True)
        output = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning("scraper_gather_failed", error=str(result))
                continue
            name, jobs = result
            output[name] = jobs
        return output

    t_start = time.monotonic()

    with Live(refresh_per_second=10, transient=True) as live:

        def update_live(msg: str) -> None:
            elapsed = round(time.monotonic() - t_start, 1)
            live.update(Text(f"  ⟳  {msg}  [{elapsed}s]", style="dim cyan"))

        update_live("connecting to job sources...")
        scraper_results = asyncio.run(_scrape_all())
        update_live("deduplicating...")

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
        sources = " · ".join(f"{name}={count}" for name, count in counts.items() if count > 0)
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
            f"[dim]Ghost filter: {len(ghost_jobs)} jobs removed ({len(all_jobs)} remaining)[/dim]"
        )
    elif ghost_jobs and is_verbose():
        console.print(f"[dim]Ghost filter removed {len(ghost_jobs)} jobs:[/dim]")
        for job, result in ghost_jobs[:5]:
            console.print(f"  [dim]✗ {job.title[:30]} @ {job.company[:20]} — {result.reason}[/dim]")

    if not all_langs:
        pre_lang = len(all_jobs)
        all_jobs = [j for j in all_jobs if _is_likely_english(j)]
        removed = pre_lang - len(all_jobs)
        if removed:
            console.print(
                f"[dim]Language filter: {removed} non-English jobs removed "
                f"(use --all-langs to include)[/dim]"
            )

    if visa_mode == "sponsor":
        pre_visa = len(all_jobs)
        all_jobs = [j for j in all_jobs if j.visa_label.value in ("confirmed", "likely")]
        removed_visa = pre_visa - len(all_jobs)
        if removed_visa:
            console.print(
                f"[dim]Visa filter: showing sponsored jobs only ({removed_visa} removed)[/dim]"
            )

    if level:
        all_jobs, level_removed = _apply_seniority_filter(all_jobs, level)
        if level_removed > 0:
            console.print(
                f"[dim]Level filter ({level}): {level_removed} jobs removed "
                f"({len(all_jobs)} remaining)[/dim]"
            )

    if not all_jobs:
        console.print("[yellow]No new jobs found.[/yellow]")
        return

    if limit > 0 and len(all_jobs) > limit:
        console.print(f"[dim]Limiting to {limit} jobs (use --limit 0 to score all)[/dim]")
        all_jobs = all_jobs[:limit]

    console.print(f"\n[bold]{len(all_jobs)} new jobs found.[/bold] Scoring now...\n")

    from nj.db.repos.enrichment_repo import EnrichmentRepo
    from nj.intel.enrichment import JobEnrichment

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

    provider_name = config.llm.provider
    concurrency = 2 if provider_name in ("groq", "freellmapi") else 5
    sem = Semaphore(concurrency)
    t_score_start = time.monotonic()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        transient=True,
    ) as progress:
        score_task = progress.add_task("Scoring with AI...", total=len(jobs_to_score))

        async def _score_all_jobs() -> list:
            async def _score_one(job):
                async with sem:
                    for attempt in range(3):
                        try:
                            result = await score_job(
                                job=job,
                                cv_base=cv_base,
                                config=config,
                                provider=provider,
                                repo=score_repo,
                            )
                            progress.advance(score_task)
                            return job, result
                        except Exception as e:
                            err = str(e)
                            if "429" in err or "rate" in err.lower():
                                wait = 2**attempt * 5
                                await asyncio.sleep(wait)
                                continue
                            logger.warning("score_failed", job_id=job.id, error=err)
                            break
                    progress.advance(score_task)
                    return None

            results = await asyncio.gather(*[_score_one(j) for j in jobs_to_score])
            return [r for r in results if r is not None]

        score_pairs = asyncio.run(_score_all_jobs())

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


def _company_website(job) -> str:
    """Extract likely company website from job URL."""
    from urllib.parse import urlparse

    url = job.url or ""
    parsed = urlparse(url)

    if "lever.co" in url:
        parts = parsed.path.strip("/").split("/")
        if parts:
            return f"https://{parts[0]}.com"

    if "greenhouse.io" in url:
        parts = parsed.path.strip("/").split("/")
        if parts:
            return f"https://{parts[0]}.com"

    if "remoteok.com" in url:
        return ""

    if not any(
        board in url
        for board in [
            "remoteok",
            "arbeitnow",
            "weworkremotely",
            "linkedin",
            "indeed",
            "glassdoor",
        ]
    ):
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""

    return ""


def _display_search_results(
    scored: list,
    blocked: int,
    dry_run: bool,
    enrichments: dict | None = None,
) -> None:
    if not scored:
        console.print(f"[yellow]No scoreable jobs.[/yellow] ({blocked} blocked by visa filter)")
        return

    enrichments = enrichments or {}
    threshold = 62

    sorted_scored = sorted(scored, key=lambda x: x[1].total_score, reverse=True)
    above_threshold = [(j, r) for j, r in sorted_scored if r.total_score >= threshold]
    below_threshold = [(j, r) for j, r in sorted_scored if r.total_score < threshold]

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
    table.add_column("Role", width=32)

    for job, result in above_threshold:
        score = result.total_score
        color = "green" if score >= 75 else "yellow"

        enrichment = enrichments.get(job.id, {})
        sponsor = enrichment.get("sponsorship") or {}
        salary_data = enrichment.get("salary") or {}

        prob = sponsor.get("probability")
        sponsor_str = f"{prob:.0%}" if prob is not None else "—"
        sponsor_color = (
            "green" if prob and prob >= 0.7 else "yellow" if prob and prob >= 0.45 else "dim"
        )

        salary_pred = salary_data.get("predicted_salary")
        salary_str = f"${salary_pred // 1000}k" if salary_pred else "—"

        role_display = _get_level_indicator(job.title) + job.title[:32]
        table.add_row(
            f"[{color}]{score}[/{color}]",
            f"[{sponsor_color}]{sponsor_str}[/{sponsor_color}]",
            salary_str,
            job.visa_label.value,
            job.company[:20],
            role_display,
        )

    console.print(table)

    if below_threshold:
        console.print(
            f"[dim]{len(below_threshold)} jobs below threshold ({threshold}) hidden. "
            f"Use --show-all to see.[/dim]"
        )

    console.print(
        f"\n[bold]{len(above_threshold)}[/bold] jobs above threshold ({threshold}). "
        f"[bold]{blocked}[/bold] blocked by visa filter.\n"
        f"Run [bold]nj review[/bold] to approve jobs for applying."
    )

    console.print(
        "\n[dim]Score = skills match (30%) + experience (25%) + "
        "role alignment (20%) + sponsorship (15%) + "
        "location (5%) + CV strength (5%)[/dim]\n"
        "[dim]Visa: confirmed=JD mentions H1B/OPT  "
        "likely=partial signals  unknown=no mention  "
        "blocked=explicitly no sponsorship[/dim]"
    )

    if above_threshold:
        console.print("\n[bold]Top jobs to apply:[/bold]\n")
        for i, (job, result) in enumerate(above_threshold[:10], 1):
            site = _company_website(job)
            site_line = f"\n      [dim]{site}[/dim]" if site else ""
            console.print(
                f"  [cyan]{i:2}.[/cyan] "
                f"[bold]{result.total_score}[/bold] "
                f"{job.title[:40]} "
                f"[dim]@ {job.company[:25]}[/dim]\n"
                f"      [dim blue]{job.url or '—'}[/dim blue]"
                f"{site_line}\n"
            )

    if dry_run:
        console.print("[dim]Dry run — no scores saved.[/dim]")
