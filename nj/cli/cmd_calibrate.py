from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console

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
