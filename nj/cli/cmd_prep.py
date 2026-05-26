from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_prep(
    config: Config,
    job_id: str | None = None,
    url: str | None = None,
    last: bool = False,
    db_path: str = "data/nj.db",
    output_dir: str = "output",
) -> None:
    from nj.providers.registry import get_provider
    from nj.tailoring.prep_generator import PrepGenerationError, generate_prep, render_prep_pdf

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print(
            "[red]cv/cv_base.json not found.[/red] "
            "Run [bold]nj init[/bold] first."
        )
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    provider = get_provider(config.llm)
    job = None
    score = None

    if url:
        job, score = _prep_from_url(url, cv_base, config, provider)
    elif job_id:
        job, score = _prep_from_db(job_id, db_path)
    elif last:
        job, score = _prep_from_last(db_path)

    if not job:
        console.print(
            "[red]No job found.[/red] "
            "Provide --job-id, --url, or --last."
        )
        return

    console.print(
        Panel(
            f"[bold]{job.title}[/bold] @ [cyan]{job.company}[/cyan]\n"
            f"[dim]Generating interview prep PDF...[/dim]",
            title="nj prep",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating prep with Claude...", total=None)
        try:
            prep_data = asyncio.run(generate_prep(job, cv_base, config, provider, score))
            progress.update(task, description="Rendering PDF...")
            pdf_path = render_prep_pdf(prep_data, job, cv_base, output_dir)
        except (PrepGenerationError, Exception) as e:
            console.print(f"[red]Prep generation failed:[/red] {e}")
            return

    console.print(f"\n[green]Interview prep ready:[/green] {pdf_path}\n")

    quick = prep_data.get("quick_reference", {})
    if quick:
        console.print(
            Panel(
                f"[bold]Role:[/bold] {quick.get('role_in_one_sentence', '')}\n\n"
                f"[bold]They want:[/bold]\n"
                + "\n".join(f"  • {w}" for w in quick.get("top_3_they_want", []))
                + "\n\n[bold]You bring:[/bold]\n"
                + "\n".join(f"  • {b}" for b in quick.get("top_3_you_bring", []))
                + f"\n\n[bold]Gap:[/bold] {quick.get('biggest_gap', '')}\n"
                f"[bold]Frame it as:[/bold] {quick.get('gap_framing', '')}",
                title="Quick reference",
                border_style="green",
            )
        )

    tech_qs = prep_data.get("technical_questions", [])
    if tech_qs:
        console.print(
            f"\n[bold]{len(tech_qs)} technical questions[/bold] "
            f"generated. Full details in PDF.\n"
        )
        console.print("[bold]Top 3 likely questions:[/bold]")
        for q in tech_qs[:3]:
            conf = q.get("confidence", "medium")
            color = "green" if conf == "high" else "yellow" if conf == "medium" else "red"
            console.print(
                f"  [{color}][{conf}][/{color}] {q.get('question', '')}"
            )

    if config.notify.email_to:
        from nj.notify.email import EmailNotifier

        notifier = EmailNotifier(config.notify)
        try:
            notifier._send(
                subject=f"nj prep: {job.title} @ {job.company}",
                body=(
                    f"Interview prep PDF for {job.title} at {job.company}.\n\n"
                    f"Top question: "
                    f"{tech_qs[0]['question'] if tech_qs else 'See PDF'}"
                ),
                attachments=[pdf_path],
            )
            console.print(f"[green]Emailed to {config.notify.email_to}[/green]")
        except Exception as e:
            logger.warning("prep_email_failed", error=str(e))


def _prep_from_url(url: str, cv_base: dict, config: Config, provider) -> tuple:
    from datetime import UTC, datetime

    import httpx

    from nj.models.job import Job, JobStatus
    from nj.scoring.scorer import score_job
    from nj.scoring.visa_filter import VisaFilter
    from nj.utils.text import clean_html, truncate

    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        description = truncate(clean_html(resp.text), 3000)
    except Exception as e:
        console.print(f"[red]Failed to fetch URL:[/red] {e}")
        return None, None

    visa_label = VisaFilter(config.visa).classify(description)
    job = Job(
        id=Job.generate_id("prep", "job", url),
        title="Job from URL",
        company="Company",
        url=url,
        description=description,
        location="",
        source="direct",
        visa_label=visa_label,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash=Job.generate_hash(description),
    )
    score = asyncio.run(score_job(job, cv_base, config, provider, repo=None))
    return job, score


def _prep_from_db(job_id: str, db_path: str) -> tuple:
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo

    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)
    jobs = job_repo.get_jobs()
    job = next((j for j in jobs if j.id == job_id), None)
    if not job:
        console.print(f"[red]Job ID not found:[/red] {job_id}")
        return None, None
    score = score_repo.get_score(job_id)
    return job, score


def _prep_from_last(db_path: str) -> tuple:
    from datetime import datetime

    from nj.db.repos.application_repo import ApplicationRepo
    from nj.models.application import ApplicationStatus

    app_repo = ApplicationRepo(db_path)
    apps = app_repo.get_applications(status=ApplicationStatus.SUBMITTED)
    if not apps:
        apps = app_repo.get_applications()
    if not apps:
        console.print("[yellow]No applications found.[/yellow]")
        return None, None
    latest = sorted(
        apps,
        key=lambda a: a.applied_at or datetime.min,
        reverse=True,
    )[0]
    return _prep_from_db(latest.job_id, db_path)
