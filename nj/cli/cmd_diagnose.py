from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.models.config import Config
from nj.models.diagnosis import HealthLevel, Severity
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

SEVERITY_COLORS = {
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
}

HEALTH_COLORS = {
    HealthLevel.WEAK: "red",
    HealthLevel.MODERATE: "yellow",
    HealthLevel.STRONG: "green",
}


def run_diagnose(
    config: Config,
    db_path: str = "data/nj.db",
    output_dir: str = "output",
    no_pdf: bool = False,
) -> None:
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo
    from nj.diagnostics.engine import DiagnosticsError, diagnose_cv
    from nj.diagnostics.renderer import render_diagnosis_pdf
    from nj.providers.registry import get_provider

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print("[red]cv/cv_base.json not found.[/red] Run [bold]nj init[/bold] first.")
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    recent_scores = []
    try:
        score_repo = ScoreRepo(db_path)
        job_repo = JobRepo(db_path)
        jobs = job_repo.get_jobs()
        for job in jobs[:50]:
            score = score_repo.get_score(job.id)
            if score:
                recent_scores.append(score.model_dump())
    except Exception:
        pass

    provider = get_provider(config.llm, task="reasoning")

    console.print(
        Panel(
            "[bold]Diagnosing your CV...[/bold]\n\n"
            "[dim]Claude is reviewing your profile from three angles:\n"
            "  • Recruiter (15-second scan)\n"
            "  • Hiring manager (depth assessment)\n"
            "  • ATS system (parseability)[/dim]",
            title="nj diagnose",
            border_style="cyan",
        )
    )

    try:
        result = asyncio.run(
            diagnose_cv(cv_base, config, provider, recent_scores or None, db_path=db_path)
        )
    except DiagnosticsError as e:
        console.print(f"[red]Diagnosis failed:[/red] {e}")
        return

    _display_diagnosis(result)

    if not no_pdf:
        try:
            pdf_path = render_diagnosis_pdf(result, cv_base, output_dir)
            console.print(f"\n[green]Full diagnosis PDF:[/green] {pdf_path}")
            if config.notify.email_to:
                from nj.notify.email import EmailNotifier

                notifier = EmailNotifier(config.notify)
                notifier._send(
                    subject="nj diagnosis: CV health report",
                    body=(
                        f"Overall health: {result.overall_health.value}\n\n"
                        f"Top recommendation:\n"
                        f"{result.top_recommendation}\n\n"
                        f"Critical issues: {len(result.critical_issues)}\n"
                        f"Full report attached."
                    ),
                    attachments=[pdf_path],
                )
                console.print(f"[green]Emailed to {config.notify.email_to}[/green]")
        except Exception as e:
            console.print(
                f"[yellow]PDF render failed:[/yellow] {e}\n"
                "[dim]Diagnosis shown above is complete.[/dim]"
            )


def _display_diagnosis(result) -> None:
    health_color = HEALTH_COLORS[result.overall_health]

    console.print(
        Panel(
            f"Overall health: "
            f"[{health_color}][bold]{result.overall_health.value.upper()}[/bold][/{health_color}]\n\n"
            f"[bold]Top recommendation:[/bold]\n"
            f"{result.top_recommendation}",
            title="Diagnosis summary",
            border_style=health_color,
        )
    )

    if result.recruiter_first_impression:
        console.print(
            Panel(
                f"[italic]{result.recruiter_first_impression}[/italic]",
                title="Recruiter first impression (15 seconds)",
                border_style="dim",
            )
        )

    if result.positioning_mismatch:
        console.print(
            Panel(
                result.positioning_mismatch,
                title="Positioning analysis",
                border_style="yellow",
            )
        )

    if result.critical_issues:
        table = Table(
            title=f"Critical issues ({len(result.critical_issues)})",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("Severity", width=9)
        table.add_column("Section", width=16)
        table.add_column("Issue", width=38)
        table.add_column("Fix", width=38)

        for issue in result.critical_issues:
            color = SEVERITY_COLORS[issue.severity]
            table.add_row(
                f"[{color}]{issue.severity.value}[/{color}]",
                issue.section,
                issue.issue[:38],
                issue.fix[:38],
            )
        console.print(table)

    if result.hidden_strengths:
        console.print("\n[bold green]Hidden strengths:[/bold green]")
        for s in result.hidden_strengths:
            console.print(f"  [green]•[/green] {s}")

    sections = []
    if result.strong_sections:
        sections.append("[green]Strong:[/green] " + ", ".join(result.strong_sections))
    if result.weak_sections:
        sections.append("[red]Needs work:[/red] " + ", ".join(result.weak_sections))
    if sections:
        console.print("\n" + "  ".join(sections))

    if result.ats_concerns:
        console.print("\n[bold yellow]ATS concerns:[/bold yellow]")
        for c in result.ats_concerns:
            console.print(f"  [yellow]•[/yellow] {c}")

    if result.score_pattern_analysis:
        console.print(
            Panel(
                result.score_pattern_analysis,
                title="Score pattern analysis",
                border_style="dim",
            )
        )
