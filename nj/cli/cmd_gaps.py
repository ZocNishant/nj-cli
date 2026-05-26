from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_gaps(
    config: Config,
    db_path: str = "data/nj.db",
    top_n: int = 10,
    min_frequency: int = 10,
) -> None:
    from nj.analytics.skill_gaps import analyze_skill_gaps
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo

    score_repo = ScoreRepo(db_path)
    job_repo = JobRepo(db_path)

    jobs = job_repo.get_jobs()
    if not jobs:
        console.print(
            "[yellow]No jobs found.[/yellow] "
            "Run [bold]nj search[/bold] first."
        )
        return

    results = []
    for job in jobs:
        score = score_repo.get_score(job.id)
        if score:
            results.append(score)

    if not results:
        console.print(
            "[yellow]No scored jobs found.[/yellow] "
            "Run [bold]nj search[/bold] (without --dry-run) first."
        )
        return

    report = analyze_skill_gaps(results, top_n=top_n)

    if not report.gaps:
        console.print(
            "[green]No significant skill gaps detected.[/green]\n"
            f"Analyzed {report.total_jobs_analyzed} jobs. "
            "Your profile covers the key skills well."
        )
        return

    _display_overview(report)
    _display_gaps_table(report, top_n)
    _display_matched_strengths(report)
    _display_recommendations(report)


def _display_overview(report) -> None:
    score_color = (
        "green"
        if report.avg_total_score >= 70
        else "yellow"
        if report.avg_total_score >= 55
        else "red"
    )
    coverage_color = (
        "green"
        if report.profile_coverage >= 70
        else "yellow"
        if report.profile_coverage >= 50
        else "red"
    )
    console.print(
        Panel(
            f"Jobs analyzed: [bold]{report.total_jobs_analyzed}[/bold]\n"
            f"Average score: [{score_color}][bold]{report.avg_total_score}/100[/bold][/{score_color}]\n"
            f"Profile coverage: [{coverage_color}][bold]{report.profile_coverage:.1f}%[/bold][/{coverage_color}] "
            f"[dim](% of mentioned skills you already have)[/dim]",
            title="nj gaps — skill gap analysis",
            border_style="cyan",
        )
    )


def _display_gaps_table(report, top_n: int) -> None:
    table = Table(
        title=f"Top skill gaps (from {report.total_jobs_analyzed} jobs)",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Rank", width=6, justify="center")
    table.add_column("Skill", width=24)
    table.add_column("In % of jobs", width=13, justify="center")
    table.add_column("Job count", width=11, justify="center")
    table.add_column("Est. score boost", width=17, justify="center")
    table.add_column("Priority", width=10)

    for i, gap in enumerate(report.gaps[:top_n], 1):
        freq = gap["frequency_pct"]
        boost = gap["estimated_score_boost"]

        freq_color = "red" if freq >= 60 else "yellow" if freq >= 35 else "dim"
        boost_color = "green" if boost >= 6 else "yellow" if boost >= 4 else "dim"
        priority = (
            "[red]HIGH[/red]"
            if freq >= 60 and boost >= 6
            else "[yellow]MED[/yellow]"
            if freq >= 35
            else "[dim]LOW[/dim]"
        )

        table.add_row(
            str(i),
            gap["skill"].title(),
            f"[{freq_color}]{freq}%[/{freq_color}]",
            str(gap["job_count"]),
            f"[{boost_color}]+{boost} pts[/{boost_color}]",
            priority,
        )

    console.print(table)


def _display_matched_strengths(report) -> None:
    if not report.matched_skill_frequency:
        return
    console.print("\n[bold green]Your strongest matched skills:[/bold green]")
    for item in report.matched_skill_frequency[:5]:
        freq = item["frequency_pct"]
        bar = "█" * (freq // 10) + "░" * (10 - freq // 10)
        console.print(
            f"  [green]{item['skill'].title():<20}[/green] "
            f"{bar} {freq}% of jobs"
        )


def _display_recommendations(report) -> None:
    if not report.gaps:
        return

    top_gap = report.gaps[0]
    console.print(
        Panel(
            f"[bold]Highest ROI gap to close:[/bold] "
            f"[cyan]{top_gap['skill'].title()}[/cyan]\n\n"
            f"Present in [bold]{top_gap['frequency_pct']}%[/bold] "
            f"of scored jobs ({top_gap['job_count']} listings).\n"
            f"Closing this gap could raise your average score by "
            f"approximately [bold]+{top_gap['estimated_score_boost']} points[/bold].\n\n"
            f"[dim]Note: Score boost is an estimate based on frequency. "
            f"Run [bold]nj calibrate --from-outcomes[/bold] after "
            f"getting interview callbacks to validate.[/dim]",
            title="Recommendation",
            border_style="green",
        )
    )

    if len(report.gaps) >= 3:
        console.print(
            "\n[dim]Other high-priority gaps: "
            + ", ".join(g["skill"].title() for g in report.gaps[1:4])
            + "[/dim]"
        )
