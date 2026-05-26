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


def run_search(
    config: Config,
    db_path: str = "data/nj.db",
    dry_run: bool = False,
) -> None:
    import asyncio

    from nj.db.engine import init_db
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo
    from nj.providers.registry import get_provider
    from nj.scrapers.indeed import IndeedScraper
    from nj.scoring.scorer import score_job
    from nj.scoring.visa_filter import VisaFilter
    from nj.utils.dedup import JobDeduplicator

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

    all_jobs = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping Indeed...", total=None)
        scraper = IndeedScraper(visa_config=config.visa)
        jobs = scraper.scrape(
            roles=config.search.roles,
            location=config.search.primary_region,
        )
        new_jobs = dedup.filter_new(jobs)
        for job in new_jobs:
            job_repo.save_job(job)
        all_jobs.extend(new_jobs)
        progress.update(
            task,
            description=f"Scraped {len(new_jobs)} new jobs from Indeed",
        )

        if config.search.include_global and not dry_run:
            progress.update(task, description="Scraping global sources...")

    if not all_jobs:
        console.print("[yellow]No new jobs found.[/yellow]")
        return

    console.print(
        f"\n[bold]{len(all_jobs)} new jobs found.[/bold] " f"Scoring now...\n"
    )

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

    _display_search_results(scored, blocked, dry_run)


def _display_search_results(
    scored: list,
    blocked: int,
    dry_run: bool,
) -> None:
    if not scored:
        console.print(
            f"[yellow]No scoreable jobs.[/yellow] "
            f"({blocked} blocked by visa filter)"
        )
        return

    table = Table(
        title="Search results",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Score", width=7, justify="center")
    table.add_column("Visa", width=11)
    table.add_column("Company", width=22)
    table.add_column("Role", width=30)
    table.add_column("Location", width=20)

    for job, result in sorted(scored, key=lambda x: x[1].total_score, reverse=True):
        score = result.total_score
        color = "green" if score >= 75 else "yellow" if score >= 60 else "red"
        table.add_row(
            f"[{color}]{score}[/{color}]",
            job.visa_label.value,
            job.company[:22],
            job.title[:30],
            job.location[:20],
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
