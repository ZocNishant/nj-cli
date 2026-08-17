from __future__ import annotations

import time

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_demo() -> None:
    console.print(
        Panel(
            "[bold cyan]nj demo[/bold cyan] — "
            "see what nj-cli produces\n\n"
            "[dim]This demo uses sample data. "
            "No API key or CV needed.\n"
            "Every output shown is what nj generates "
            "from your real CV + real jobs.[/dim]",
            border_style="cyan",
        )
    )

    input("\nPress Enter to start the demo...")

    _demo_search()
    input("\nPress Enter to see scoring...")

    _demo_score()
    input("\nPress Enter to see diagnosis...")

    _demo_diagnose()
    input("\nPress Enter to see skill gaps...")

    _demo_gaps()
    input("\nPress Enter to finish...")

    _demo_summary()


def _demo_search() -> None:
    console.print(Rule("[dim]nj search --dry-run[/dim]"))
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scraping RemoteOK...", total=None)
        time.sleep(1.2)
        progress.update(task, description="Found 118 ML jobs")
        time.sleep(0.5)
        progress.update(task, description="Deduplicating...")
        time.sleep(0.4)

    console.print("[green]✓[/green] 118 new jobs found  [dim](1 blocked by visa filter)[/dim]")
    console.print("[dim]Sources: remoteok=118  linkedin=0 (needs cookie)  indeed=0 (blocked)[/dim]")
    console.print()


def _demo_score() -> None:
    from nj.demo.sample_data import SAMPLE_JOB, SAMPLE_SCORE

    console.print(Rule("[dim]nj review — sample scored job[/dim]"))
    console.print()

    score = SAMPLE_SCORE
    total = score["total_score"]
    color = "green" if total >= 75 else "yellow" if total >= 60 else "red"

    table = Table(box=box.SIMPLE, show_header=True, pad_edge=False)
    table.add_column("Category", style="dim", width=28)
    table.add_column("Score", width=7, justify="center")
    table.add_column("Rationale", width=50)

    for sub in score["sub_scores"]:
        s = sub["score"]
        sc = "green" if s >= 75 else "yellow" if s >= 60 else "red"
        table.add_row(
            sub["category"].replace("_", " ").title(),
            f"[{sc}]{s}[/{sc}]",
            sub["rationale"][:50],
        )

    console.print(
        Panel(
            f"[bold]{SAMPLE_JOB['title']}[/bold] "
            f"@ [cyan]{SAMPLE_JOB['company']}[/cyan]  "
            f"[dim]{SAMPLE_JOB['location']}[/dim]  "
            f"visa: [green]{SAMPLE_JOB['visa_label']}[/green]\n\n"
            f"Total score: [{color}][bold]{total}/100[/bold][/{color}]  "
            f"confidence: {score['confidence']}\n\n"
            f"{score['overall_rationale']}\n",
            title="Job 1/118",
            border_style=color,
        )
    )
    console.print(table)
    console.print(f"\nMatched: [green]{', '.join(score['matched_skills'][:5])}[/green]")
    console.print(f"Missing: [red]{', '.join(score['missing_skills'])}[/red]")
    console.print(f"Emphasise: {', '.join(score['recommended_emphasis'])}")
    console.print()


def _demo_diagnose() -> None:
    from nj.demo.sample_data import SAMPLE_DIAGNOSIS

    d = SAMPLE_DIAGNOSIS
    console.print(Rule("[dim]nj diagnose[/dim]"))
    console.print()

    health = d["overall_health"]
    health_color = "green" if health == "strong" else "yellow" if health == "moderate" else "red"

    console.print(
        Panel(
            f"Overall health: [{health_color}][bold]{health.upper()}[/bold][/{health_color}]\n\n"
            f"[bold]Top recommendation:[/bold]\n"
            f"{d['top_recommendation']}",
            title="CV diagnosis",
            border_style=health_color,
        )
    )

    console.print(
        Panel(
            f"[italic]{d['recruiter_first_impression']}[/italic]",
            title="Recruiter first impression (15 seconds)",
            border_style="dim",
        )
    )

    issue_table = Table(title="Critical issues", box=box.ROUNDED, show_lines=True)
    issue_table.add_column("Severity", width=9)
    issue_table.add_column("Section", width=14)
    issue_table.add_column("Issue", width=42)
    issue_table.add_column("Fix", width=40)

    severity_colors = {"high": "red", "medium": "yellow", "low": "blue"}
    for issue in d["critical_issues"]:
        c = severity_colors.get(issue["severity"], "white")
        issue_table.add_row(
            f"[{c}]{issue['severity']}[/{c}]",
            issue["section"],
            issue["issue"][:42],
            issue["fix"][:40],
        )
    console.print(issue_table)

    console.print("\n[bold green]Hidden strengths:[/bold green]")
    for s in d["hidden_strengths"]:
        console.print(f"  [green]•[/green] {s}")
    console.print()


def _demo_gaps() -> None:
    from nj.demo.sample_data import SAMPLE_GAPS

    console.print(Rule("[dim]nj gaps[/dim]"))
    console.print()

    console.print(
        Panel(
            "Jobs analyzed: [bold]118[/bold]\n"
            "Average score: [yellow][bold]67.3/100[/bold][/yellow]\n"
            "Profile coverage: [yellow][bold]74.2%[/bold][/yellow] "
            "[dim](% of mentioned skills you already have)[/dim]",
            title="Skill gap overview",
            border_style="cyan",
        )
    )

    table = Table(title="Top skill gaps", box=box.ROUNDED)
    table.add_column("Rank", width=6, justify="center")
    table.add_column("Skill", width=18)
    table.add_column("In % of jobs", width=13, justify="center")
    table.add_column("Est. boost", width=12, justify="center")
    table.add_column("Priority", width=10)

    for i, gap in enumerate(SAMPLE_GAPS, 1):
        freq = gap["frequency_pct"]
        boost = gap["estimated_score_boost"]
        freq_color = "red" if freq >= 60 else "yellow" if freq >= 35 else "dim"
        boost_color = "green" if boost >= 6 else "yellow"
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
            f"[{boost_color}]+{boost} pts[/{boost_color}]",
            priority,
        )
    console.print(table)

    top = SAMPLE_GAPS[0]
    console.print(
        Panel(
            f"[bold]Highest ROI gap:[/bold] "
            f"[cyan]{top['skill'].title()}[/cyan]\n\n"
            f"Present in [bold]{top['frequency_pct']}%[/bold] "
            f"of 118 scored jobs.\n"
            f"Closing this gap could raise your average score by "
            f"approximately [bold]+{top['estimated_score_boost']} points[/bold].",
            title="Recommendation",
            border_style="green",
        )
    )
    console.print()


def _demo_summary() -> None:
    console.print(Rule())
    console.print(
        Panel(
            "[bold]Demo complete.[/bold]\n\n"
            "What you just saw is what nj generates from your "
            "real CV and real job listings.\n\n"
            "[bold]To get started:[/bold]\n\n"
            "  1. Get an Anthropic API key → console.anthropic.com\n"
            "  2. [bold]nj init[/bold]          — setup wizard\n"
            "  3. [bold]nj search[/bold]        — find and score real jobs\n"
            "  4. [bold]nj diagnose[/bold]      — get your CV diagnosis\n"
            "  5. [bold]nj gaps[/bold]          — see your skill gaps\n"
            "  6. [bold]nj review[/bold]        — approve jobs for applying\n\n"
            "[dim]API cost: ~$0.10-0.30 per 30-job search run[/dim]",
            title="nj-cli",
            border_style="cyan",
        )
    )
