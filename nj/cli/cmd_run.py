from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console

from nj.models.application import ApplicationRecord, ApplicationStatus
from nj.models.config import Config
from nj.models.job import JobStatus
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def _get_enabled_scrapers(config: Config) -> list:
    import os

    scrapers = []

    li_at = os.getenv("LINKEDIN_LI_AT", "")
    if li_at and config.scraper.linkedin_enabled:
        from nj.scrapers.linkedin import LinkedInScraper

        scrapers.append(
            LinkedInScraper(session_cookie=li_at, visa_config=config.visa, headless=True)
        )

    if config.scraper.adzuna_enabled:
        from nj.scrapers.indeed import AdzunaScraper

        adzuna_id = os.getenv("ADZUNA_APP_ID", config.scraper.adzuna_app_id)
        adzuna_key = os.getenv("ADZUNA_APP_KEY", config.scraper.adzuna_app_key)
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

    if not scrapers:
        from nj.scrapers.remoteok import RemoteOKScraper

        scrapers.append(RemoteOKScraper(visa_config=config.visa))

    return scrapers


def run_pipeline(
    config: Config,
    db_path: str = "data/nj.db",
    dry_run: bool = False,
    silent: bool = False,
) -> None:
    from nj.applying.anti_bot import RateLimiter
    from nj.db.engine import init_db
    from nj.db.repos.application_repo import ApplicationRepo
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo
    from nj.notify.email import EmailNotifier
    from nj.providers.registry import get_provider
    from nj.scoring.scorer import score_job
    from nj.scoring.visa_filter import VisaFilter
    from nj.tailoring.cover_letter import generate_and_save_cover_letter
    from nj.tailoring.renderer import render_cv
    from nj.tailoring.tailor import tailor_cv

    init_db(db_path)
    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)
    app_repo = ApplicationRepo(db_path)
    provider = get_provider(config.llm)
    visa_filter = VisaFilter(config.visa)
    notifier = EmailNotifier(config.notify)
    rate_limiter = RateLimiter(
        delay_min=config.apply.delay_min,
        delay_max=config.apply.delay_max,
        max_per_day=config.apply.max_per_day,
    )

    if not silent:
        console.print("\n[bold cyan]nj run[/bold cyan] — starting pipeline\n")

    if not config.apply.enabled and not dry_run:
        if not silent:
            console.print(
                "[yellow]apply.enabled is False — "
                "running in search+score mode only.[/yellow]\n"
                "Set [bold]apply.enabled: true[/bold] in config.yaml "
                "to enable applying.\n"
            )

    today_count = app_repo.count_today()
    if today_count >= config.apply.max_per_day:
        if not silent:
            console.print(
                f"[yellow]Daily limit reached "
                f"({today_count}/{config.apply.max_per_day}).[/yellow] "
                "Try again tomorrow."
            )
        return

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print(
            "[red]cv/cv_base.json not found.[/red] " "Run [bold]nj init[/bold] first."
        )
        return
    with open(cv_path) as f:
        cv_base = json.load(f)

    from nj.utils.dedup import JobDeduplicator

    dedup = JobDeduplicator(job_repo)

    from nj.utils.logger import is_verbose

    if not silent:
        console.print("[dim]Phase 1: Scraping...[/dim]")
    scrapers = _get_enabled_scrapers(config)
    all_raw_jobs: list = []
    counts: dict[str, int] = {}
    for scraper in scrapers:
        try:
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
    if not silent:
        if not is_verbose():
            console.print(
                f"  [green]✓[/green] [bold]{len(new_jobs)}[/bold] new jobs  "
                f"[dim]({len(all_raw_jobs) - len(new_jobs)} duplicates skipped)[/dim]"
            )
            console.print(
                "  [dim]Sources: "
                + " · ".join(
                    f"{s.name()}={counts.get(s.name(), 0)}" for s in scrapers
                )
                + "[/dim]\n"
            )
        else:
            console.print(
                f"  Found [bold]{len(new_jobs)}[/bold] new jobs "
                f"({len(all_raw_jobs) - len(new_jobs)} duplicates skipped)\n"
            )

    if not new_jobs:
        if not silent:
            console.print("[yellow]No new jobs to process.[/yellow]")
        return

    if not silent:
        console.print("[dim]Phase 2: Scoring...[/dim]")

    applications: list[dict] = []
    processed = 0

    for job in new_jobs:
        if visa_filter.should_skip(job):
            record = ApplicationRecord.create(job.id, 0)
            record.status = ApplicationStatus.SKIPPED_VISA
            app_repo.save_application(record)
            continue

        result = asyncio.run(score_job(job, cv_base, config, provider, score_repo))

        if result.total_score < config.scoring.threshold:
            record = ApplicationRecord.create(job.id, result.total_score)
            record.status = ApplicationStatus.SKIPPED_THRESHOLD
            app_repo.save_application(record)
            if not silent:
                console.print(
                    f"  [dim]Skip {job.title[:30]} @ "
                    f"{job.company[:20]} "
                    f"(score {result.total_score} < "
                    f"{config.scoring.threshold})[/dim]"
                )
            continue

        job_repo.update_job_status(job.id, JobStatus.PENDING_REVIEW)

        if config.apply.automation_phase == 1:
            if not silent:
                console.print(
                    f"  [green]Queued for review:[/green] "
                    f"{job.title[:30]} @ {job.company[:20]} "
                    f"(score {result.total_score})"
                )
            continue

        if not silent:
            console.print(
                f"  [dim]Tailoring CV for "
                f"{job.title[:30]} @ {job.company[:20]}...[/dim]"
            )
        tailored_cv, _ = asyncio.run(tailor_cv(job, result, cv_base, config, provider))
        job_repo.update_job_status(job.id, JobStatus.TAILORED)

        template_path = "templates/cv_template.tex"
        pdf_path = None
        if Path(template_path).exists() and not dry_run:
            try:
                pdf_path = render_cv(
                    cv_data=tailored_cv,
                    template_path=template_path,
                    output_dir="output",
                    company=job.company,
                    job_title=job.title,
                )
            except Exception as e:
                logger.warning("render_failed", job_id=job.id, error=str(e))

        cover_path = None
        if not dry_run:
            cover_path = asyncio.run(
                generate_and_save_cover_letter(job, result, cv_base, provider, "output")
            )

        from nj.models.quality import GateDecision
        from nj.scoring.quality_gate import check_application_quality

        gate = check_application_quality(
            job=job,
            tailored_cv=tailored_cv,
            cover_letter=cover_path or "",
            score=result,
            config=config,
        )

        if gate.decision == GateDecision.BLOCKED:
            if not silent:
                console.print(
                    f"  [red]✗ Blocked:[/red] "
                    f"{job.title[:25]} @ {job.company[:20]} — "
                    f"{gate.blocking_reasons[0] if gate.blocking_reasons else 'quality gate'}"
                )
            record = ApplicationRecord.create(job.id, result.total_score)
            record.status = ApplicationStatus.FAILED
            record.error_message = (
                f"quality_gate_blocked: {'; '.join(gate.blocking_reasons)}"
            )
            app_repo.save_application(record)
            continue

        if gate.has_warnings and not silent:
            console.print(
                f"  [yellow]⚠ Warnings:[/yellow] "
                f"{', '.join(gate.warnings[:2])}"
            )

        record = ApplicationRecord.create(job.id, result.total_score)

        if config.apply.enabled and not dry_run:
            if not rate_limiter.can_apply():
                if not silent:
                    console.print("[yellow]Daily limit reached mid-run.[/yellow]")
                break
            record.cv_path = pdf_path
            record.cover_letter_path = cover_path
            record.status = ApplicationStatus.SUBMITTED
            app_repo.save_application(record)
            rate_limiter.record_application()
            if not silent:
                notifier.send_application_email(
                    job_title=job.title,
                    company=job.company,
                    job_url=job.url,
                    score=result.total_score,
                    confidence=result.confidence,
                    matched_skills=result.matched_skills,
                    missing_skills=result.missing_skills,
                    visa_label=job.visa_label.value,
                    visa_notes=result.visa_notes,
                    cv_path=pdf_path,
                    cover_letter_path=cover_path,
                )
            applications.append(
                {
                    "score": result.total_score,
                    "status": "submitted",
                    "company": job.company,
                    "title": job.title,
                    "visa_label": job.visa_label.value,
                }
            )
            processed += 1
        else:
            record.status = ApplicationStatus.PENDING
            app_repo.save_application(record)

    if applications and not dry_run:
        notifier.send_daily_summary(applications)

    if not silent:
        _print_run_summary(
            new_jobs=len(new_jobs),
            processed=processed,
            dry_run=dry_run,
            phase=config.apply.automation_phase,
        )


def _print_run_summary(
    new_jobs: int,
    processed: int,
    dry_run: bool,
    phase: int,
) -> None:
    console.print("\n[bold]Run complete.[/bold]")
    console.print(f"  New jobs scraped:  {new_jobs}")
    console.print(f"  Processed:         {processed}")
    if dry_run:
        console.print("  [dim]Dry run — no applications submitted.[/dim]")
    if phase == 1:
        console.print(
            "\n  Phase 1 mode: jobs queued for review.\n"
            "  Run [bold]nj review[/bold] to approve jobs."
        )
