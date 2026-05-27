from __future__ import annotations

import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.models.config import Config
from nj.models.quality import GateDecision
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

DECISION_COLORS = {
    GateDecision.APPROVED: "green",
    GateDecision.WARNING: "yellow",
    GateDecision.BLOCKED: "red",
}

DECISION_ICONS = {
    GateDecision.APPROVED: "✓",
    GateDecision.WARNING: "⚠",
    GateDecision.BLOCKED: "✗",
}


def run_quality_check(
    config: Config,
    job_id: str | None = None,
    db_path: str = "data/nj.db",
) -> None:
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo
    from nj.scoring.quality_gate import check_application_quality

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print(
            "[red]cv/cv_base.json not found.[/red] "
            "Run [bold]nj init[/bold] first."
        )
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)

    if job_id:
        jobs = job_repo.get_jobs()
        job = next((j for j in jobs if j.id == job_id), None)
        if not job:
            console.print(
                f"[red]Job '{job_id}' not found.[/red] "
                "Run [bold]nj status[/bold] to see job IDs."
            )
            return
        score = score_repo.get_score(job_id)
        if not score:
            console.print(
                f"[yellow]No score found for job '{job_id}'.[/yellow] "
                "Run [bold]nj search[/bold] first."
            )
            return
        _check_and_display(job, cv_base, "", score, config)
    else:
        from nj.models.job import JobStatus

        tailored = job_repo.get_jobs(status=JobStatus.TAILORED)
        if not tailored:
            console.print(
                "[yellow]No tailored jobs found.[/yellow]\n"
                "Run [bold]nj review[/bold] and approve jobs first."
            )
            return
        console.print(f"\n[bold]Checking {len(tailored)} tailored jobs...[/bold]\n")
        for job in tailored:
            score = score_repo.get_score(job.id)
            if score:
                _check_and_display(job, cv_base, "", score, config)
                console.print()


def _check_and_display(job, cv_base, cover_letter, score, config) -> None:
    from nj.scoring.quality_gate import check_application_quality

    result = check_application_quality(
        job=job,
        tailored_cv=cv_base,
        cover_letter=cover_letter,
        score=score,
        config=config,
    )
    color = DECISION_COLORS[result.decision]
    icon = DECISION_ICONS[result.decision]

    console.print(
        Panel(
            f"[{color}][bold]{icon} {result.decision.value.upper()}[/bold][/{color}]\n\n"
            f"[bold]{job.title}[/bold] @ {job.company}\n"
            f"Score: {result.score_at_check}/100  "
            f"Confidence: {result.confidence:.2f}\n\n"
            f"[bold]Recommendation:[/bold] {result.recommendation}",
            title="Quality gate",
            border_style=color,
        )
    )

    if result.blocking_reasons:
        console.print("[bold red]Blocking reasons:[/bold red]")
        for r in result.blocking_reasons:
            console.print(f"  [red]✗[/red] {r}")

    if result.warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for w in result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {w}")

    if result.issues:
        table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        table.add_column("Category", width=16)
        table.add_column("Issue", width=50)
        table.add_column("Blocking", width=10)
        for issue in result.issues:
            blocking_str = "[red]yes[/red]" if issue.blocking else "[dim]no[/dim]"
            table.add_row(issue.category, issue.issue[:50], blocking_str)
        console.print(table)
