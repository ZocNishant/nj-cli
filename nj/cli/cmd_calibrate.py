from __future__ import annotations

from pathlib import Path

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.models.config import Config
from nj.scoring.calibration import display_calibration_table, prompt_threshold
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_calibrate(
    config: Config,
    db_path: str = "data/nj.db",
    config_path: str = "config.yaml",
) -> None:
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo

    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)

    scored_jobs = job_repo.get_jobs()
    if not scored_jobs:
        console.print("[yellow]No scored jobs found.[/yellow]")
        console.print("Run [bold]nj search[/bold] first to score some jobs.")
        return

    results = []
    for job in scored_jobs:
        result = score_repo.get_score(job.id)
        if result:
            results.append(result)

    if not results:
        console.print("[yellow]No score results found.[/yellow]")
        return

    console.print(f"\n[bold]nj calibrate[/bold] — " f"{len(results)} scored jobs\n")
    display_calibration_table(scored_jobs, results)

    scores = sorted([r.total_score for r in results])
    if scores:
        p40_idx = int(len(scores) * 0.40)
        p40 = scores[p40_idx]
        console.print(
            f"\n[dim]Score distribution: "
            f"min={scores[0]}  "
            f"p40={p40}  "
            f"median={scores[len(scores)//2]}  "
            f"max={scores[-1]}[/dim]"
        )

    current = config.scoring.threshold
    new_threshold = prompt_threshold(current)

    if new_threshold and new_threshold != current:
        _save_threshold(new_threshold, config_path)
        console.print(
            f"\n[green]Threshold updated:[/green] " f"{current} → {new_threshold}"
        )
        console.print(f"[dim]Saved to {config_path}[/dim]")
    else:
        console.print(f"\n[dim]Threshold unchanged: {current}[/dim]")


def run_calibrate_from_outcomes(
    config: Config,
    db_path: str = "data/nj.db",
    config_path: str = "config.yaml",
) -> None:
    from nj.analytics.outcomes import analyze_outcomes
    from nj.db.repos.application_repo import ApplicationRepo
    from nj.db.repos.score_repo import ScoreRepo

    app_repo = ApplicationRepo(db_path)
    score_repo = ScoreRepo(db_path)

    applications = app_repo.get_applications_with_outcomes()
    if not applications:
        console.print(
            "[yellow]No outcome data yet.[/yellow]\n"
            "Run [bold]nj watch[/bold] after applying to collect callbacks."
        )
        return

    all_scores = score_repo.get_all_scores()
    score_results = {s.job_id: s for s in all_scores}

    report = analyze_outcomes(applications, score_results)

    console.print(
        Panel(
            f"[bold]{report.total_with_outcomes}[/bold] applications with outcomes  "
            f"· [bold]{len(report.score_outcome_pairs)}[/bold] matched to scores",
            title="[bold cyan]nj calibrate --from-outcomes[/bold cyan]",
            border_style="cyan",
        )
    )

    if report.interview_rate_by_score_band:
        table = Table(box=box.ROUNDED, show_lines=False)
        table.add_column("Score band", width=12)
        table.add_column("Interview rate", width=16, justify="center")
        table.add_column("Signal", width=10)

        for band in ["50-59", "60-69", "70-79", "80-89", "90-100"]:
            rate = report.interview_rate_by_score_band.get(band)
            if rate is None:
                continue
            color = "green" if rate >= 25 else "yellow" if rate >= 10 else "red"
            marker = "✓ optimal" if (
                report.optimal_threshold is not None
                and band.startswith(str(report.optimal_threshold))
            ) else ""
            table.add_row(
                band,
                f"[{color}]{rate}%[/{color}]",
                f"[dim]{marker}[/dim]",
            )

        console.print(table)

    if report.avg_score_interviews or report.avg_score_rejections:
        console.print(
            f"\n  Avg score (interviews): [green]{report.avg_score_interviews}[/green]  "
            f"Avg score (rejections): [red]{report.avg_score_rejections}[/red]"
        )

    console.print(f"\n[italic]{report.recommendation}[/italic]\n")

    if report.optimal_threshold:
        current = config.scoring.threshold
        console.print(
            f"Current threshold: [bold]{current}[/bold]  "
            f"Suggested: [bold green]{report.optimal_threshold}[/bold green]"
        )
        from rich.prompt import Confirm
        if Confirm.ask(
            f"Update threshold to {report.optimal_threshold}?", default=False
        ):
            _save_threshold(report.optimal_threshold, config_path)
            console.print(
                f"[green]Threshold updated:[/green] {current} → {report.optimal_threshold}"
            )
        else:
            console.print(f"[dim]Threshold unchanged: {current}[/dim]")


def _save_threshold(threshold: int, config_path: str) -> None:
    p = Path(config_path)
    if p.exists():
        with open(p) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    if "scoring" not in data:
        data["scoring"] = {}
    data["scoring"]["threshold"] = threshold
    with open(p, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
