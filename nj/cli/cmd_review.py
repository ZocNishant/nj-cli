from __future__ import annotations

import webbrowser
from datetime import UTC, datetime

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.db.repos.job_repo import JobRepo
from nj.db.repos.label_repo import LabelRepo
from nj.db.repos.score_repo import ScoreRepo
from nj.models.config import Config
from nj.models.job import Job, JobStatus
from nj.models.label import JobLabel, LabelValue
from nj.models.score import ScoreResult
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def _score_color(score: int) -> str:
    if score >= 75:
        return "green"
    elif score >= 60:
        return "yellow"
    return "red"


def _render_score_table(result: ScoreResult) -> Table:
    table = Table(box=box.SIMPLE, show_header=True, pad_edge=False)
    table.add_column("Category", style="dim", width=26)
    table.add_column("Score", width=7, justify="center")
    table.add_column("Rationale", width=48)
    for sub in result.sub_scores:
        color = _score_color(sub.score)
        score_str = f"[{color}]{sub.score}[/{color}]"
        table.add_row(
            sub.category.value.replace("_", " ").title(),
            score_str,
            sub.rationale[:48],
        )
    return table


def _render_job_panel(
    job: Job,
    result: ScoreResult,
    index: int,
    total: int,
) -> Panel:
    color = _score_color(result.total_score)
    header = (
        f"[bold]{job.title}[/bold] @ [cyan]{job.company}[/cyan]  "
        f"[dim]{job.location}[/dim]  "
        f"[dim]source: {job.source}[/dim]  "
        f"visa: [{color}]{job.visa_label.value}[/{color}]"
    )
    score_line = (
        f"Total score: [{color}]{result.total_score}/100[/{color}]  "
        f"confidence: {result.confidence:.2f}"
    )
    matched = (
        "[green]" + ", ".join(result.matched_skills[:6]) + "[/green]"
        if result.matched_skills
        else "[dim]none[/dim]"
    )
    missing = (
        "[red]" + ", ".join(result.missing_skills[:4]) + "[/red]"
        if result.missing_skills
        else "[dim]none[/dim]"
    )
    emphasis = ", ".join(result.recommended_emphasis[:3]) if result.recommended_emphasis else "none"
    jd_excerpt = job.description[:280].strip()
    if len(job.description) > 280:
        jd_excerpt += "..."

    content = f"{header}\n{score_line}\n\n[bold]Rationale:[/bold] {result.overall_rationale}\n\n"
    content += str(_render_score_table(result)) + "\n"
    content += (
        f"[bold]Matched:[/bold] {matched}\n"
        f"[bold]Missing:[/bold] {missing}\n"
        f"[bold]Emphasise:[/bold] {emphasis}\n\n"
        f"[bold]JD excerpt:[/bold]\n[dim]{jd_excerpt}[/dim]\n"
    )
    return Panel(
        content,
        title=f"[dim]Job {index}/{total}[/dim]",
        border_style=color,
        padding=(1, 2),
    )


def _get_keypress() -> str:
    try:
        import readchar

        return readchar.readchar().lower()
    except ImportError:
        return console.input("").strip().lower()[:1]


def run_review(
    config: Config,
    db_path: str = "data/nj.db",
    limit: int = 50,
) -> None:
    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)
    label_repo = LabelRepo(db_path)

    pending = job_repo.get_jobs(status=JobStatus.PENDING_REVIEW)
    if not pending:
        console.print("[yellow]No jobs pending review.[/yellow]")
        console.print("Run [bold]nj search[/bold] first to populate the queue.")
        return

    pending = pending[:limit]
    total = len(pending)
    applied = skipped = labeled = 0

    console.print(f"\n[bold]nj review[/bold] — {total} jobs in queue\n")
    console.print(
        "Keys: [green]a[/green]=approve  "
        "[red]s[/red]=skip  "
        "[blue]l[/blue]=label  "
        "[cyan]v[/cyan]=view in browser  "
        "[dim]q[/dim]=quit\n"
    )

    for i, job in enumerate(pending, 1):
        result = score_repo.get_score(job.id)
        if not result:
            logger.warning("review_no_score", job_id=job.id)
            continue

        console.print(_render_job_panel(job, result, i, total))

        while True:
            console.print(
                f"  [dim]({i}/{total})[/dim]  "
                "[green]a[/green] approve  "
                "[red]s[/red] skip  "
                "[blue]l[/blue] label  "
                "[cyan]v[/cyan] view  "
                "[dim]q[/dim] quit  > ",
                end="",
            )
            key = _get_keypress()
            console.print(key)

            if key == "a":
                job_repo.update_job_status(job.id, JobStatus.TAILORED)
                console.print(
                    f"  [green]Approved[/green] — {job.title} @ {job.company} added to apply queue."
                )
                applied += 1
                break

            elif key == "s":
                job_repo.update_job_status(job.id, JobStatus.SKIPPED)
                console.print("  [dim]Skipped.[/dim]")
                skipped += 1
                break

            elif key == "l":
                console.print(
                    "\n  Label this job — "
                    "[green]y[/green]=yes  "
                    "[red]n[/red]=no  "
                    "[yellow]m[/yellow]=maybe  > ",
                    end="",
                )
                lkey = _get_keypress()
                console.print(lkey)
                label_map = {
                    "y": LabelValue.YES,
                    "n": LabelValue.NO,
                    "m": LabelValue.MAYBE,
                }
                if lkey in label_map:
                    rationale = (
                        console.input("  Reason (optional, Enter to skip): ").strip() or None
                    )
                    label = JobLabel(
                        job_id=job.id,
                        label=label_map[lkey],
                        user_rationale=rationale,
                        labeled_at=datetime.now(UTC),
                        score_at_label_time=result.total_score,
                    )
                    label_repo.save_label(label)
                    job_repo.update_job_status(job.id, JobStatus.SKIPPED)
                    console.print(
                        f"  [blue]Labeled {lkey}[/blue] and saved to calibration dataset."
                    )
                    labeled += 1
                break

            elif key == "v":
                webbrowser.open(job.url)
                console.print("  [cyan]Opened in browser.[/cyan]")

            elif key == "q":
                console.print("\n[dim]Review session ended.[/dim]")
                _print_session_summary(applied, skipped, labeled, total)
                return

            else:
                console.print("  [dim]Unknown key. Use a/s/l/v/q.[/dim]")

        console.print()

    console.print("\n[bold]Review complete.[/bold]")
    _print_session_summary(applied, skipped, labeled, total)


def _print_session_summary(
    applied: int,
    skipped: int,
    labeled: int,
    total: int,
) -> None:
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column(width=20)
    table.add_column(width=10, justify="right")
    table.add_row("Approved for apply", f"[green]{applied}[/green]")
    table.add_row("Skipped", f"[red]{skipped}[/red]")
    table.add_row("Labeled", f"[blue]{labeled}[/blue]")
    table.add_row("Total reviewed", str(applied + skipped + labeled))
    table.add_row("Remaining", str(total - applied - skipped - labeled))
    console.print(Panel(table, title="Session summary", border_style="dim"))
