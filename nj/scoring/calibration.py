from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table

from nj.models.job import Job
from nj.models.score import ScoreResult
from nj.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


def display_calibration_table(
    jobs: list[Job],
    results: list[ScoreResult],
) -> None:
    table = Table(
        title="Scoring calibration results",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Score", style="bold", width=7, justify="center")
    table.add_column("Conf", width=6, justify="center")
    table.add_column("Visa", width=10)
    table.add_column("Title", width=28)
    table.add_column("Company", width=20)
    table.add_column("Matched skills", width=30)

    job_map = {j.id: j for j in jobs}
    sorted_results = sorted(results, key=lambda r: r.total_score, reverse=True)

    for result in sorted_results:
        job = job_map.get(result.job_id)
        if not job:
            continue
        score = result.total_score
        if score >= 75:
            score_str = f"[green]{score}[/green]"
        elif score >= 60:
            score_str = f"[yellow]{score}[/yellow]"
        else:
            score_str = f"[red]{score}[/red]"

        conf_str = f"{result.confidence:.1f}"
        visa_str = job.visa_label.value
        matched = ", ".join(result.matched_skills[:3])

        table.add_row(
            score_str,
            conf_str,
            visa_str,
            job.title[:28],
            job.company[:20],
            matched[:30],
        )

    console.print(table)


def prompt_threshold(current: int = 62) -> int | None:
    console.print(f"\nCurrent threshold: [bold]{current}[/bold]")
    console.print("Jobs above threshold will proceed to tailoring and review.")
    raw = console.input(f"\nEnter new threshold [50-90] or press Enter to keep {current}: ").strip()
    if not raw:
        return None
    try:
        value = int(raw)
        if 50 <= value <= 90:
            return value
        console.print("[red]Must be between 50 and 90.[/red]")
        return None
    except ValueError:
        console.print("[red]Invalid number.[/red]")
        return None
