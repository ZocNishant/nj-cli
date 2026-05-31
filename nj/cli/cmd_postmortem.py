from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_postmortem(
    config: Config,
    db_path: str = "data/nj.db",
    min_applications: int = 3,
) -> None:
    from nj.db.repos.application_repo import ApplicationRepo
    from nj.db.repos.score_repo import ScoreRepo
    from nj.db.repos.job_repo import JobRepo
    from nj.analytics.outcomes_analysis import analyze_postmortem

    app_repo = ApplicationRepo(db_path)
    score_repo = ScoreRepo(db_path)
    job_repo = JobRepo(db_path)

    applications = app_repo.get_applications()
    if not applications:
        console.print(
            "[yellow]No applications found.[/yellow]\n"
            "Run [bold]nj run[/bold] or "
            "[bold]nj review[/bold] to start applying."
        )
        return

    if len(applications) < min_applications:
        console.print(
            f"[yellow]Only {len(applications)} "
            f"application(s) found.[/yellow]\n"
            f"Postmortem needs at least "
            f"{min_applications} to find patterns.\n"
            f"Keep applying and come back."
        )
        return

    scores = {}
    for app in applications:
        score = score_repo.get_score(app.job_id)
        if score:
            scores[app.job_id] = score

    jobs_list = job_repo.get_jobs()
    jobs = {j.id: j for j in jobs_list}

    report = analyze_postmortem(applications, scores, jobs)
    _display_postmortem(report)


def _display_postmortem(report) -> None:
    rate_color = (
        "green" if report.interview_rate >= 20
        else "yellow" if report.interview_rate >= 10
        else "red"
    )
    console.print(Panel(
        f"[bold]Application Postmortem[/bold]\n\n"
        f"Total applications:  [bold]{report.total_applications}[/bold]\n"
        f"With outcomes:       [bold]{report.total_with_outcomes}[/bold]\n\n"
        f"Interview rate:      [{rate_color}][bold]{report.interview_rate}%[/bold][/{rate_color}]\n"
        f"Rejection rate:      [red]{report.rejection_rate}%[/red]\n"
        f"No response rate:    [dim]{report.no_response_rate}%[/dim]",
        title="nj postmortem",
        border_style=rate_color,
    ))

    console.print(Rule("[dim]Score analysis[/dim]"))
    console.print(
        f"  Average score (all):        [cyan]{report.avg_score_all}[/cyan]\n"
        f"  Average score (interviews): [green]{report.avg_score_interviews}[/green]\n"
        f"  Average score (rejections): [red]{report.avg_score_rejections}[/red]"
    )

    if report.score_distribution:
        console.print("\n[bold]Score distribution:[/bold]")
        for band, count in sorted(report.score_distribution.items(), reverse=True):
            if count == 0:
                continue
            bar = "█" * min(count * 2, 20)
            color = (
                "green" if band.startswith("8") or band.startswith("9")
                else "yellow" if band.startswith("7")
                else "red"
            )
            console.print(
                f"  [dim]{band:>8}[/dim] [{color}]{bar}[/{color}] {count}"
            )

    if report.patterns:
        console.print(Rule("[dim]Patterns detected[/dim]"))
        for pattern in report.patterns:
            color = (
                "red" if pattern.severity == "high"
                else "yellow" if pattern.severity == "medium"
                else "dim"
            )
            console.print(
                f"\n  [{color}][bold][{pattern.severity.upper()}][/bold][/{color}] "
                f"{pattern.description}"
            )
            for evidence in pattern.evidence[:2]:
                console.print(f"    [dim]→ {evidence}[/dim]")
            console.print(f"    [cyan]Fix:[/cyan] {pattern.recommendation}")

    if report.role_type_analysis:
        console.print(Rule("[dim]Performance by role type[/dim]"))
        table = Table(box=box.SIMPLE, show_header=True, pad_edge=False)
        table.add_column("Role type", width=18)
        table.add_column("Applications", width=14, justify="center")
        table.add_column("Interviews", width=12, justify="center")
        table.add_column("Interview rate", width=15, justify="center")
        table.add_column("Avg score", width=10, justify="center")
        for role, data in sorted(
            report.role_type_analysis.items(),
            key=lambda x: x[1]["interview_rate"],
            reverse=True,
        ):
            rate = data["interview_rate"]
            rate_color = (
                "green" if rate >= 20
                else "yellow" if rate >= 10
                else "red" if data["total"] >= 3
                else "dim"
            )
            table.add_row(
                role,
                str(data["total"]),
                str(data["interviews"]),
                f"[{rate_color}]{rate}%[/{rate_color}]",
                str(data["avg_score"]),
            )
        console.print(table)

    if report.skill_gap_patterns:
        console.print(Rule("[dim]Skills missing in rejected applications[/dim]"))
        for gap in report.skill_gap_patterns[:6]:
            bar_len = min(int(gap["pct_of_rejections"] / 5), 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            console.print(
                f"  [red]{bar}[/red] "
                f"[bold]{gap['skill']:<20}[/bold] "
                f"[dim]missing in {gap['pct_of_rejections']}% of rejections[/dim]"
            )

    if report.recommendations:
        console.print(Rule("[dim]Recommendations[/dim]"))
        for i, rec in enumerate(report.recommendations, 1):
            console.print(f"  [cyan]{i}.[/cyan] {rec}")
        console.print()
