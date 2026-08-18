from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def _job_from_url(url: str, config: Config):
    """Build a throwaway Job by fetching a posting we have never seen.

    Everything here is a guess: the title and company are unknown, and the
    description is whatever `clean_html` salvages from the page — on a
    JavaScript-rendered board that is page furniture, not the posting. Prefer
    `--job-id` whenever the job is already in the database.
    """
    from datetime import UTC, datetime

    import httpx

    from nj.models.job import Job, JobStatus
    from nj.scoring.visa_filter import VisaFilter
    from nj.utils.text import clean_html, truncate

    console.print(f"[dim]Fetching job from {url}...[/dim]")
    resp = httpx.get(url, timeout=15, follow_redirects=True)
    description = truncate(clean_html(resp.text), 3000)

    return Job(
        id=Job.generate_id("direct", "job", url),
        title="Job from URL",
        company="Company",
        url=url,
        description=description,
        location="",
        source="direct",
        visa_label=VisaFilter(config.visa).classify(description),
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash=Job.generate_hash(description),
    )


def _record_application(
    app_repo,
    job,
    score: int,
    pdf_path: str | None,
    cover_path: str | None,
) -> None:
    """Log the generated packet so a human can later mark it sent.

    Without this row there is no id for
    `nj status --update-id <id> --update-status submitted`, so the moment you
    send the CV the system has no memory of it: nothing counts against
    `apply.max_per_day`, nothing appears on the dashboard, and there is no
    record for an interview or rejection to attach to — which is why the
    outcome analytics have never had data to read.

    Three rules, each load-bearing:

    * **No PDF, no row.** `ApplicationStatus.GENERATED` asserts that a CV and
      letter are on disk. If the render failed or ran past the page budget
      there is nothing to send, and a row claiming otherwise is the exact lie
      the GENERATED/SUBMITTED split exists to prevent.
    * **Never SUBMITTED.** nj cannot send anything; only a human promotes a row.
    * **A human's promotion is never undone.** Re-tailoring a job you have
      already sent refreshes the paths and the score but leaves the status
      alone. Overwriting SUBMITTED with GENERATED would silently retract an
      application you actually made.
    """
    from datetime import UTC, datetime

    from nj.models.application import ApplicationRecord, ApplicationStatus

    if not pdf_path:
        logger.info("application_not_recorded_no_pdf", job_id=job.id)
        return

    now = datetime.now(UTC).replace(tzinfo=None)
    existing = app_repo.get_by_job_id(job.id)

    if existing is not None:
        # Same status back in: update_status writes the paths and score without
        # touching a verdict a human already gave.
        app_repo.update_status(
            existing.id,
            existing.status,
            cv_path=pdf_path,
            cover_letter_path=cover_path,
            score=score,
            applied_at=existing.applied_at or now,
        )
        console.print(
            f"[dim]Application record updated:[/dim] [bold]{existing.id}[/bold] "
            f"([bold]{existing.status.value}[/bold])"
        )
        return

    record = ApplicationRecord.create(job.id, score)
    record.cv_path = pdf_path
    record.cover_letter_path = cover_path
    record.status = ApplicationStatus.GENERATED
    # count_today() filters on applied_at; unset, the daily cap counts zero.
    record.applied_at = now
    app_repo.save_application(record)

    console.print(
        f"[green]Logged as[/green] [bold]{record.id}[/bold] "
        f"[dim](generated — nothing sent)[/dim]\n"
        f"[dim]After you send it:[/dim] "
        f"nj status --update-id {record.id} --update-status submitted"
    )


def run_tailor(
    url: str | None,
    config: Config,
    db_path: str = "data/nj.db",
    output_dir: str = "output",
    job_id: str | None = None,
) -> None:
    from nj.db.repos.application_repo import ApplicationRepo
    from nj.db.repos.job_repo import JobRepo
    from nj.providers.registry import get_provider
    from nj.scoring.scorer import score_job
    from nj.tailoring.cover_letter import generate_and_save_cover_letter
    from nj.tailoring.renderer import PageBudgetError, render_cv
    from nj.tailoring.tailor import tailor_cv

    if bool(url) == bool(job_id):
        console.print("[red]Pass exactly one of[/red] URL [red]or[/red] --job-id.")
        return

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print("[red]cv/cv_base.json not found.[/red] Run [bold]nj init[/bold] first.")
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    if job_id:
        job = JobRepo(db_path).get_job(job_id)
        if job is None:
            console.print(
                f"[red]No job matching[/red] {job_id}. "
                "Run [bold]nj search[/bold] or [bold]nj review[/bold] to list ids."
            )
            return
        console.print(f"[dim]{job.title} @ {job.company}[/dim]")
    else:
        try:
            job = _job_from_url(url, config)
        except Exception as e:
            console.print(f"[red]Failed to fetch URL:[/red] {e}")
            return
        # Stored so the application row written below has a job to resolve
        # against — `nj status` looks the title and company up by job_id, and a
        # dangling reference degrades to a blank line. The id is derived from
        # the URL, so re-running on the same posting updates rather than
        # duplicates.
        JobRepo(db_path).save_job(job)

    provider = get_provider(config.llm, task="tailoring")
    # Audits the drafter's output on the cheap tier before anything is rendered.
    review_provider = get_provider(config.llm, task="review")
    console.print("[dim]Scoring...[/dim]")
    result = asyncio.run(score_job(job, cv_base, config, provider, repo=None))

    console.print("[dim]Tailoring CV (draft → adversarial review)...[/dim]")
    tailored_cv, cover_letter = asyncio.run(
        tailor_cv(job, result, cv_base, config, provider, review_provider=review_provider)
    )

    template_path = "templates/cv_template.tex"
    pdf_path = None
    if Path(template_path).exists():
        try:
            pdf_path = render_cv(
                cv_data=tailored_cv,
                template_path=template_path,
                output_dir=output_dir,
                company=job.company,
                job_title=job.title,
            )
            console.print(f"[green]CV rendered:[/green] {pdf_path}")
        except PageBudgetError as e:
            # The PDF exists and is worth looking at — it just runs long. Say so
            # distinctly, or this reads as a compile failure.
            console.print(
                f"[yellow]CV ran to {e.pages} pages (budget {e.max_pages}).[/yellow] "
                f"Not attached. Trim it and re-run: {e.pdf_path}"
            )
        except Exception as e:
            console.print(f"[yellow]PDF render failed:[/yellow] {e}")

    # Saves the letter that already went through the reviewer, rather than
    # paying for a second, unreviewed one.
    cover_path = asyncio.run(
        generate_and_save_cover_letter(
            job, result, cv_base, provider, output_dir, content=cover_letter
        )
    )
    if cover_path:
        console.print(f"[green]Cover letter:[/green] {cover_path}")
    else:
        # No file is written in this case, by design. Say so, or the operator
        # sends the CV believing a letter went with it.
        console.print("[yellow]Cover letter failed — no file written.[/yellow] See logs.")

    _record_application(
        app_repo=ApplicationRepo(db_path),
        job=job,
        score=result.total_score,
        pdf_path=pdf_path,
        cover_path=cover_path,
    )

    if config.notify.email_to:
        from nj.notify.email import EmailNotifier

        notifier = EmailNotifier(config.notify)
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
        console.print(f"[green]Emailed to {config.notify.email_to}[/green]")

    console.print(
        Panel(
            f"Score: [bold]{result.total_score}/100[/bold]  "
            f"confidence: {result.confidence:.2f}\n\n"
            f"{result.overall_rationale}\n\n"
            f"Matched: {', '.join(result.matched_skills[:5])}\n"
            f"Missing: {', '.join(result.missing_skills[:3])}",
            title=f"Results — {job.title} @ {job.company}"[:70],
            border_style="cyan",
        )
    )
