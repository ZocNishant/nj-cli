from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich import box

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_diff(
    config: Config,
    job_id: str | None = None,
    db_path: str = "data/nj.db",
    section: str | None = None,
) -> None:
    from nj.db.repos.job_repo import JobRepo
    from nj.db.repos.score_repo import ScoreRepo

    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print(
            "[red]cv/cv_base.json not found.[/red] "
            "Run [bold]nj init[/bold] first."
        )
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)

    if not job_id:
        _show_available_jobs(job_repo, score_repo)
        return

    jobs = job_repo.get_jobs()
    job = next(
        (j for j in jobs if j.id.startswith(job_id)),
        None,
    )
    if not job:
        console.print(
            f"[red]Job '{job_id}' not found.[/red]\n"
            "Run [bold]nj diff[/bold] to see available jobs."
        )
        return

    score = score_repo.get_score(job.id)

    output_dir = Path("output")
    tailored_cv = _find_tailored_cv(output_dir, job)

    if not tailored_cv:
        console.print(
            f"[yellow]No tailored CV found for this job.[/yellow]\n"
            f"Run [bold]nj tailor --url {job.url}[/bold] first."
        )
        return

    _display_diff(cv_base, tailored_cv, job, score, section)


def _find_tailored_cv(output_dir: Path, job) -> dict | None:
    safe_company = _safe_name(job.company)
    safe_title = _safe_name(job.title)

    if not output_dir.exists():
        return None

    for f in output_dir.glob("*.json"):
        if (
            safe_company[:8].lower() in f.name.lower()
            or safe_title[:8].lower() in f.name.lower()
        ):
            try:
                return json.loads(f.read_text())
            except Exception:
                continue
    return None


def _safe_name(text: str) -> str:
    return re.sub(r"[^\w]", "_", text)[:20]


def _show_available_jobs(job_repo, score_repo) -> None:
    jobs = job_repo.get_jobs()
    if not jobs:
        console.print(
            "[yellow]No jobs found.[/yellow] "
            "Run [bold]nj search[/bold] first."
        )
        return

    output_dir = Path("output")
    tailored_jobs = []
    for job in jobs:
        tailored = _find_tailored_cv(output_dir, job)
        if tailored:
            score = score_repo.get_score(job.id)
            tailored_jobs.append((job, score, tailored))

    if not tailored_jobs:
        console.print(
            "[yellow]No tailored CVs found.[/yellow]\n"
            "Run [bold]nj tailor --url URL[/bold] or "
            "[bold]nj run[/bold] to generate tailored CVs."
        )
        return

    table = Table(
        title="Jobs with tailored CVs",
        box=box.ROUNDED,
    )
    table.add_column("ID (first 8)", width=10, style="dim")
    table.add_column("Company", width=22)
    table.add_column("Role", width=30)
    table.add_column("Score", min_width=5, justify="center")

    for job, score, _ in tailored_jobs:
        s = score.total_score if score else 0
        color = (
            "green" if s >= 75
            else "yellow" if s >= 60
            else "red"
        )
        table.add_row(
            job.id[:8],
            job.company[:22],
            job.title[:30],
            f"[{color}]{s}[/{color}]",
        )
    console.print(table)
    console.print(
        "\n[dim]Run [bold]nj diff --job-id ID[/bold] "
        "to see what changed.[/dim]"
    )


def _display_diff(
    cv_base: dict,
    tailored: dict,
    job,
    score,
    section: str | None,
) -> None:
    console.print(Panel(
        f"[bold]{job.title}[/bold] @ "
        f"[cyan]{job.company}[/cyan]\n"
        f"[dim]Diff: base CV → tailored CV[/dim]",
        title="nj diff",
        border_style="cyan",
    ))

    sections_to_diff = (
        [section] if section
        else ["summary", "skills", "experience", "projects"]
    )

    for sec in sections_to_diff:
        base_val = cv_base.get(sec)
        tail_val = tailored.get(sec)
        if base_val is None and tail_val is None:
            continue
        _diff_section(sec, base_val, tail_val)


def _diff_section(section: str, base, tailored) -> None:
    console.print(Rule(f"[dim]{section.upper()}[/dim]"))

    if section == "summary":
        _diff_summary(base, tailored)
    elif section == "skills":
        _diff_skills(base, tailored)
    elif section == "experience":
        _diff_experience(base, tailored)
    elif section == "projects":
        _diff_projects(base, tailored)
    else:
        _diff_generic(section, base, tailored)


def _diff_summary(base: str, tailored: str) -> None:
    if not base and not tailored:
        return
    if not base and tailored:
        console.print(
            "[green]+ ADDED summary:[/green]\n"
            f"  {tailored}"
        )
        return
    if base == tailored:
        console.print("[dim]  No change.[/dim]")
        return
    console.print("[red]− Base:[/red]")
    console.print(f"  [dim]{base or '(empty)'}[/dim]")
    console.print("[green]+ Tailored:[/green]")
    console.print(f"  {tailored or '(empty)'}")


def _diff_skills(base: dict | None, tailored: dict | None) -> None:
    if not base and not tailored:
        return
    base = base or {}
    tailored = tailored or {}

    all_categories = set(base.keys()) | set(tailored.keys())
    any_change = False

    for cat in sorted(all_categories):
        base_skills = set(base.get(cat, []))
        tail_skills = set(tailored.get(cat, []))
        added = tail_skills - base_skills
        removed = base_skills - tail_skills

        if added or removed:
            any_change = True
            console.print(
                f"\n  [bold]{cat.replace('_', ' ').title()}[/bold]"
            )
            for s in sorted(added):
                console.print(f"    [green]+ {s}[/green]")
            for s in sorted(removed):
                console.print(f"    [red]− {s}[/red]")

    if not any_change:
        console.print("[dim]  No changes in skills.[/dim]")


def _diff_experience(base: list | None, tailored: list | None) -> None:
    base = base or []
    tailored = tailored or []

    base_map = {
        e.get("id", e.get("company", i)): e
        for i, e in enumerate(base)
        if isinstance(e, dict)
    }
    tail_map = {
        e.get("id", e.get("company", i)): e
        for i, e in enumerate(tailored)
        if isinstance(e, dict)
    }

    any_change = False
    for key in base_map:
        base_exp = base_map[key]
        tail_exp = tail_map.get(key)
        if not tail_exp:
            console.print(
                f"\n  [red]− REMOVED:[/red] "
                f"{base_exp.get('title', key)} "
                f"@ {base_exp.get('company', '')}"
            )
            any_change = True
            continue

        base_bullets = base_exp.get("bullets", [])
        tail_bullets = tail_exp.get("bullets", [])

        if base_bullets != tail_bullets:
            any_change = True
            title = base_exp.get("title", key)
            company = base_exp.get("company", "")
            console.print(f"\n  [bold]{title}[/bold] @ {company}")
            _diff_bullet_lists(base_bullets, tail_bullets)

    if not any_change:
        console.print("[dim]  No changes in experience.[/dim]")


def _diff_projects(base: list | None, tailored: list | None) -> None:
    base = base or []
    tailored = tailored or []

    base_map = {
        p.get("id", p.get("name", i)): p
        for i, p in enumerate(base)
        if isinstance(p, dict)
    }
    tail_map = {
        p.get("id", p.get("name", i)): p
        for i, p in enumerate(tailored)
        if isinstance(p, dict)
    }

    base_order = [
        p.get("id", p.get("name", ""))
        for p in base if isinstance(p, dict)
    ]
    tail_order = [
        p.get("id", p.get("name", ""))
        for p in tailored if isinstance(p, dict)
    ]

    if base_order != tail_order and tail_order:
        console.print("\n  [yellow]~ ORDER CHANGED:[/yellow]")
        console.print(
            f"  Base:     {' → '.join(str(x)[:12] for x in base_order[:4])}"
        )
        console.print(
            f"  Tailored: {' → '.join(str(x)[:12] for x in tail_order[:4])}"
        )

    any_bullet_change = False
    for key in base_map:
        base_proj = base_map[key]
        tail_proj = tail_map.get(key)
        if not tail_proj:
            continue
        base_bullets = base_proj.get("bullets", [])
        tail_bullets = tail_proj.get("bullets", [])
        if base_bullets != tail_bullets:
            any_bullet_change = True
            name = base_proj.get("name", key)
            console.print(f"\n  [bold]{name}[/bold]")
            _diff_bullet_lists(base_bullets, tail_bullets)

    if base_order == tail_order and not any_bullet_change:
        console.print("[dim]  No changes in projects.[/dim]")


def _diff_bullet_lists(base: list[str], tailored: list[str]) -> None:
    base_set = set(base)
    tail_set = set(tailored)

    added = [b for b in tailored if b not in base_set]
    removed = [b for b in base if b not in tail_set]

    paired = []
    remaining_added = list(added)
    remaining_removed = list(removed)

    for rem in removed[:]:
        best_match = None
        best_score = 0
        rem_words = set(rem.lower().split())
        for add in remaining_added:
            add_words = set(add.lower().split())
            if not rem_words or not add_words:
                continue
            overlap = len(rem_words & add_words) / max(
                len(rem_words), len(add_words)
            )
            if overlap > 0.4 and overlap > best_score:
                best_score = overlap
                best_match = add
        if best_match:
            paired.append((rem, best_match))
            remaining_removed.remove(rem)
            remaining_added.remove(best_match)

    for old, new in paired:
        console.print("    [yellow]~ REWRITTEN:[/yellow]")
        console.print(f"      [red]− {old[:80]}[/red]")
        console.print(f"      [green]+ {new[:80]}[/green]")

    for b in remaining_added:
        console.print(f"    [green]+ ADDED:   {b[:80]}[/green]")

    for b in remaining_removed:
        console.print(f"    [red]− REMOVED: {b[:80]}[/red]")


def _diff_generic(section: str, base, tailored) -> None:
    if base == tailored:
        console.print("[dim]  No change.[/dim]")
    else:
        console.print(
            f"[red]− {base}[/red]\n"
            f"[green]+ {tailored}[/green]"
        )
