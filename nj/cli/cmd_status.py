from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.db.repos.application_repo import ApplicationRepo
from nj.db.repos.job_repo import JobRepo
from nj.models.application import ApplicationStatus
from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

STATUS_COLORS = {
    "submitted": "green",
    "applied": "green",
    "interview": "blue",
    "pending": "yellow",
    "failed": "red",
    "rejected": "red",
    "captcha_blocked": "red",
    "bot_detected": "red",
    "skipped_threshold": "dim",
    "skipped_visa": "dim",
}


def run_status(
    config: Config,
    db_path: str = "data/nj.db",
    update_id: str | None = None,
    update_status: str | None = None,
) -> None:
    app_repo = ApplicationRepo(db_path)
    job_repo = JobRepo(db_path)

    if update_id and update_status:
        try:
            status = ApplicationStatus(update_status)
            app_repo.update_status(update_id, status)
            console.print(
                f"[green]Updated[/green] application [bold]{update_id}[/bold] "
                f"to [bold]{update_status}[/bold]"
            )
            return
        except ValueError:
            console.print(
                f"[red]Invalid status:[/red] {update_status}\n"
                f"Valid values: {[s.value for s in ApplicationStatus]}"
            )
            return

    applications = app_repo.get_applications()
    if not applications:
        console.print("[yellow]No applications yet.[/yellow]")
        console.print(
            "Run [bold]nj search[/bold] to find jobs, "
            "then [bold]nj review[/bold] to approve them."
        )
        return

    table = Table(
        title="nj — application tracker",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
    )
    table.add_column("Date", width=12, style="dim")
    table.add_column("Company", width=20)
    table.add_column("Role", width=28)
    table.add_column("Score", width=7, justify="center")
    table.add_column("Visa", width=11)
    table.add_column("Status", width=16)

    job_map = {}
    for app in applications:
        for j in job_repo.get_jobs():
            if j.id == app.job_id:
                job_map[app.job_id] = j
                break

    sorted_apps = sorted(
        applications,
        key=lambda a: a.applied_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    for app in sorted_apps:
        job = job_map.get(app.job_id)
        company = job.company[:20] if job else "Unknown"
        title = job.title[:28] if job else "Unknown"
        visa = job.visa_label.value[:11] if job else ""
        date_str = app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "—"
        status_val = app.status.value
        color = STATUS_COLORS.get(status_val, "white")
        score_color = (
            "green" if app.score >= 75 else "yellow" if app.score >= 60 else "red"
        )
        table.add_row(
            date_str,
            company,
            title,
            f"[{score_color}]{app.score}[/{score_color}]",
            visa,
            f"[{color}]{status_val}[/{color}]",
        )

    console.print(table)
    _print_stats(applications)


def _print_stats(applications: list) -> None:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    submitted = [a for a in applications if a.status.value in ("submitted", "applied")]
    this_week = [
        a
        for a in submitted
        if a.applied_at and a.applied_at.replace(tzinfo=UTC) >= week_ago
    ]
    this_month = [
        a
        for a in submitted
        if a.applied_at and a.applied_at.replace(tzinfo=UTC) >= month_ago
    ]
    avg_score = sum(a.score for a in submitted) / len(submitted) if submitted else 0
    interviews = sum(1 for a in applications if a.status.value == "interview")

    stats = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    stats.add_column(width=28, style="dim")
    stats.add_column(width=10, justify="right")
    stats.add_row("Applied this week", str(len(this_week)))
    stats.add_row("Applied this month", str(len(this_month)))
    stats.add_row("Average score (applied)", f"{avg_score:.1f}")
    stats.add_row("Interviews", f"[blue]{interviews}[/blue]")
    console.print(Panel(stats, title="Stats", border_style="dim"))
