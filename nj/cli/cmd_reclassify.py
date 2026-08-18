"""Re-derive stored visa labels with the current classifier.

`jobs.visa_label` is written once, at scrape time, by whatever version of the
classifier was in the tree that day. Fixing `nj/scoring/visa_filter.py` does not
touch a single stored row, so a database can keep serving labels from a matcher
that was replaced months ago — and `VisaFilter.should_skip` and `nj search` both
read the stored value, not a fresh one.

That is not hypothetical. The substring matcher this replaced labelled 224 jobs
"sponsorship confirmed" when only 7 of them contained the word "sponsor"; the
rest matched `opt` inside `optimization`. Those rows survived the fix.

Read-only by default. `--apply` is what writes.
"""

from __future__ import annotations

from collections import Counter

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.models.config import Config
from nj.models.job import Job, VisaLabel
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

# Worst case first. A job wrongly marked CONFIRMED is the expensive direction:
# it survives the filter, gets scored and tailored, and an application goes to
# an employer who never offered to sponsor. A job wrongly marked BLOCKED is
# merely invisible.
_FLIP_SEVERITY = {
    # Worst of all: the posting explicitly refuses sponsorship and was stored as
    # confirmed. Strictly worse than CONFIRMED -> UNKNOWN, which is only the
    # absence of a signal rather than a stated refusal.
    (VisaLabel.CONFIRMED, VisaLabel.BLOCKED): 0,
    (VisaLabel.CONFIRMED, VisaLabel.UNKNOWN): 1,
    (VisaLabel.LIKELY, VisaLabel.BLOCKED): 2,
    (VisaLabel.UNKNOWN, VisaLabel.BLOCKED): 3,
    (VisaLabel.BLOCKED, VisaLabel.CONFIRMED): 4,
    (VisaLabel.UNKNOWN, VisaLabel.CONFIRMED): 5,
}
_DEFAULT_SEVERITY = 6

_LABEL_STYLE = {
    VisaLabel.CONFIRMED: "green",
    VisaLabel.LIKELY: "cyan",
    VisaLabel.UNKNOWN: "yellow",
    VisaLabel.BLOCKED: "red",
}


def _styled(label: VisaLabel) -> str:
    return f"[{_LABEL_STYLE.get(label, 'white')}]{label.value}[/]"


class Reclassification:
    """One job's old label, its freshly derived label, and the evidence."""

    __slots__ = ("job", "old", "new", "evidence")

    def __init__(self, job: Job, old: VisaLabel, new: VisaLabel, evidence: str) -> None:
        self.job = job
        self.old = old
        self.new = new
        self.evidence = evidence

    @property
    def flipped(self) -> bool:
        return self.old != self.new

    @property
    def severity(self) -> int:
        return _FLIP_SEVERITY.get((self.old, self.new), _DEFAULT_SEVERITY)


def reclassify_jobs(jobs: list[Job], config: Config) -> list[Reclassification]:
    """Derive a current label for every job. Pure — touches no storage.

    Separated from the command so the interesting logic is testable without a
    database, a console, or a confirmation prompt.
    """
    from nj.scoring.visa_filter import VisaFilter

    visa_filter = VisaFilter(config.visa)
    results: list[Reclassification] = []
    for job in jobs:
        try:
            new_label, evidence = visa_filter.explain(job.description or "")
        except Exception as e:  # a bad row must not abort the whole sweep
            logger.warning("reclassify_failed", job_id=job.id, error=str(e))
            continue
        results.append(Reclassification(job, job.visa_label, new_label, evidence))
    return results


def _print_distribution(results: list[Reclassification]) -> None:
    before = Counter(r.old for r in results)
    after = Counter(r.new for r in results)

    table = Table(box=box.SIMPLE, title=None)
    table.add_column("Label", style="bold")
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Change", justify="right")

    for label in (VisaLabel.CONFIRMED, VisaLabel.LIKELY, VisaLabel.UNKNOWN, VisaLabel.BLOCKED):
        b, a = before.get(label, 0), after.get(label, 0)
        delta = a - b
        if delta > 0:
            change = f"[green]+{delta}[/green]"
        elif delta < 0:
            change = f"[red]{delta}[/red]"
        else:
            change = "[dim]0[/dim]"
        table.add_row(_styled(label), str(b), str(a), change)

    console.print(Panel(table, title="Label distribution", border_style="dim"))


def _print_flip_matrix(flips: list[Reclassification]) -> None:
    counts = Counter((r.old, r.new) for r in flips)
    table = Table(box=box.SIMPLE)
    table.add_column("From", style="bold")
    table.add_column("To", style="bold")
    table.add_column("Jobs", justify="right")

    for (old, new), n in sorted(
        counts.items(), key=lambda kv: (_FLIP_SEVERITY.get(kv[0], _DEFAULT_SEVERITY), -kv[1])
    ):
        table.add_row(_styled(old), _styled(new), str(n))

    console.print(Panel(table, title="What moves", border_style="dim"))


def _print_sample(flips: list[Reclassification], sample: int) -> None:
    # Most consequential first, so a reviewer reading only the top of the list
    # is reading the rows that actually matter.
    ordered = sorted(flips, key=lambda r: (r.severity, r.job.company or ""))
    shown = ordered[:sample]

    table = Table(box=box.SIMPLE, show_lines=True)
    table.add_column("Job", style="bold", max_width=34, overflow="fold")
    table.add_column("Was", max_width=10)
    table.add_column("Now", max_width=10)
    table.add_column("Why the classifier says so", overflow="fold")

    for r in shown:
        title = (r.job.title or "")[:40]
        company = (r.job.company or "")[:26]
        table.add_row(
            f"{title}\n[dim]{company}[/dim]",
            _styled(r.old),
            _styled(r.new),
            r.evidence,
        )

    console.print(
        Panel(
            table,
            title=f"Sample of changes ({len(shown)} of {len(flips)}, most consequential first)",
            border_style="dim",
        )
    )
    if len(flips) > len(shown):
        console.print(
            f"  [dim]{len(flips) - len(shown)} more — rerun with "
            f"[bold]--sample {len(flips)}[/bold] to see all.[/dim]\n"
        )


def run_reclassify(
    config: Config,
    db_path: str = "data/nj.db",
    apply: bool = False,
    sample: int = 10,
) -> None:
    """Re-derive every stored visa label and report what would change."""
    from nj.db.repos.job_repo import JobRepo

    repo = JobRepo(db_path)
    jobs = repo.get_jobs()

    if not jobs:
        console.print("[yellow]No jobs in the database.[/yellow] Run [bold]nj search[/bold] first.")
        return

    if not config.visa.enabled:
        console.print(
            "[yellow]visa.enabled is false in config.yaml.[/yellow]\n"
            "The classifier returns UNKNOWN for everything while it is off, so "
            "reclassifying now would erase every label. Nothing was changed."
        )
        return

    console.print(f"\n[bold cyan]nj reclassify[/bold cyan] — {len(jobs)} jobs\n")

    results = reclassify_jobs(jobs, config)
    flips = [r for r in results if r.flipped]

    _print_distribution(results)

    if not flips:
        console.print(
            "\n[green]Every stored label already matches the current "
            "classifier.[/green] Nothing to do.\n"
        )
        return

    _print_flip_matrix(flips)
    _print_sample(flips, sample)

    pct = 100.0 * len(flips) / len(results)
    console.print(
        f"  [bold]{len(flips)}[/bold] of {len(results)} labels would change ({pct:.0f}%).\n"
    )

    if not apply:
        console.print(
            Panel(
                "Nothing was written. Review the sample above, then rerun with "
                "[bold]--apply[/bold] to update the database.",
                border_style="yellow",
                title="Dry run",
            )
        )
        return

    changed = repo.update_visa_labels({r.job.id: r.new for r in flips})
    logger.info("visa_labels_reclassified", changed=changed, total=len(results))
    console.print(f"[green]✓ Updated {changed} labels.[/green]\n")
