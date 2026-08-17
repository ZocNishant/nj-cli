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


def run_tailor(
    url: str,
    config: Config,
    db_path: str = "data/nj.db",
    output_dir: str = "output",
) -> None:
    from datetime import UTC, datetime

    import httpx

    from nj.models.job import Job, JobStatus
    from nj.providers.registry import get_provider
    from nj.scoring.scorer import score_job
    from nj.scoring.visa_filter import VisaFilter
    from nj.tailoring.cover_letter import generate_and_save_cover_letter
    from nj.tailoring.renderer import PageBudgetError, render_cv
    from nj.tailoring.tailor import tailor_cv

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print("[red]cv/cv_base.json not found.[/red] Run [bold]nj init[/bold] first.")
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    console.print(f"[dim]Fetching job from {url}...[/dim]")
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        from nj.utils.text import clean_html, truncate

        description = truncate(clean_html(resp.text), 3000)
    except Exception as e:
        console.print(f"[red]Failed to fetch URL:[/red] {e}")
        return

    job = Job(
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
    console.print(f"[green]Cover letter:[/green] {cover_path}")

    if config.notify.email_to:
        from nj.notify.email import EmailNotifier

        notifier = EmailNotifier(config.notify)
        notifier.send_application_email(
            job_title=job.title,
            company=job.company,
            job_url=url,
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
            title=f"Results — {url[:60]}",
            border_style="cyan",
        )
    )
