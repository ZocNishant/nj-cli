from __future__ import annotations

from datetime import UTC, datetime

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.db.repos.label_repo import LabelRepo
from nj.models.config import Config
from nj.models.label import JobLabel, LabelValue
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def _get_keypress() -> str:
    try:
        import readchar

        return readchar.readchar().lower()
    except ImportError:
        return console.input("").strip().lower()[:1]


def run_label(
    config: Config,
    db_path: str = "data/nj.db",
    show_stats: bool = False,
) -> None:
    label_repo = LabelRepo(db_path)

    if show_stats:
        _show_label_stats(label_repo)
        return

    unlabeled = label_repo.get_unlabeled_scored_jobs(limit=20)
    if not unlabeled:
        console.print("[yellow]No unlabeled scored jobs found.[/yellow]")
        console.print(
            "Run [bold]nj search[/bold] to score more jobs, "
            "or [bold]nj label --stats[/bold] to see your dataset."
        )
        return

    total = len(unlabeled)
    labeled_count = 0
    console.print(
        f"\n[bold]nj label[/bold] — {total} jobs to label\n"
        f"[dim]Keys: [green]y[/green]=yes  "
        f"[red]n[/red]=no  [yellow]m[/yellow]=maybe  "
        f"[dim]s[/dim]=skip  [dim]q[/dim]=quit[/dim]\n"
    )

    for i, (job, result) in enumerate(unlabeled, 1):
        color = (
            "green" if result.total_score >= 75 else "yellow" if result.total_score >= 60 else "red"
        )
        panel_content = (
            f"[bold]{job.title}[/bold] @ [cyan]{job.company}[/cyan]  "
            f"[dim]{job.location}[/dim]\n"
            f"Score: [{color}]{result.total_score}/100[/{color}]  "
            f"confidence: {result.confidence:.2f}  "
            f"visa: {job.visa_label.value}\n\n"
            f"[dim]{result.overall_rationale}[/dim]\n\n"
            f"Matched: [green]{', '.join(result.matched_skills[:5])}[/green]\n"
            f"Missing: [red]{', '.join(result.missing_skills[:3])}[/red]"
        )
        console.print(
            Panel(
                panel_content,
                title=f"[dim]{i}/{total}[/dim]",
                border_style=color,
            )
        )
        console.print(
            "  Label: [green]y[/green]=yes  "
            "[red]n[/red]=no  [yellow]m[/yellow]=maybe  "
            "[dim]s[/dim]=skip  [dim]q[/dim]=quit  > ",
            end="",
        )
        key = _get_keypress()
        console.print(key)

        label_map = {
            "y": LabelValue.YES,
            "n": LabelValue.NO,
            "m": LabelValue.MAYBE,
        }
        if key == "q":
            console.print("\n[dim]Labeling session ended.[/dim]")
            break
        elif key == "s":
            console.print("  [dim]Skipped.[/dim]\n")
            continue
        elif key in label_map:
            rationale = console.input("  Reason (optional): ").strip() or None
            label = JobLabel(
                job_id=job.id,
                label=label_map[key],
                user_rationale=rationale,
                labeled_at=datetime.now(UTC),
                score_at_label_time=result.total_score,
            )
            label_repo.save_label(label)
            labeled_count += 1
            console.print(f"  [blue]Saved label: {key}[/blue]\n")
        else:
            console.print("  [dim]Unknown key.[/dim]\n")

    all_labels = label_repo.get_labels()
    console.print(
        f"\n[bold]Labeled {labeled_count} jobs.[/bold]  "
        f"Dataset size: [cyan]{len(all_labels)}[/cyan] total labels."
    )


def _show_label_stats(label_repo: LabelRepo) -> None:
    labels = label_repo.get_labels()
    if not labels:
        console.print("[yellow]No labels yet.[/yellow]")
        return
    yes = [lb for lb in labels if lb.label == LabelValue.YES]
    no = [lb for lb in labels if lb.label == LabelValue.NO]
    maybe = [lb for lb in labels if lb.label == LabelValue.MAYBE]
    avg_yes = sum(lb.score_at_label_time for lb in yes) / len(yes) if yes else 0
    avg_no = sum(lb.score_at_label_time for lb in no) / len(no) if no else 0
    avg_maybe = sum(lb.score_at_label_time for lb in maybe) / len(maybe) if maybe else 0

    table = Table(
        title="Calibration dataset",
        box=box.ROUNDED,
    )
    table.add_column("Label", width=10)
    table.add_column("Count", width=8, justify="right")
    table.add_column("Avg score", width=12, justify="right")
    table.add_row("[green]yes[/green]", str(len(yes)), f"{avg_yes:.1f}")
    table.add_row("[red]no[/red]", str(len(no)), f"{avg_no:.1f}")
    table.add_row("[yellow]maybe[/yellow]", str(len(maybe)), f"{avg_maybe:.1f}")
    table.add_row("[bold]total[/bold]", f"[bold]{len(labels)}[/bold]", "")
    console.print(table)
