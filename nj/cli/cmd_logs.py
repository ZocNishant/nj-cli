from __future__ import annotations

from pathlib import Path

from rich.console import Console

from nj.models.config import Config

console = Console()


def run_logs(
    config: Config,
    last_n: int = 20,
    log_file: str = "logs/nj.log",
    show_stats: bool = False,
    db_path: str = "data/nj.db",
) -> None:
    if show_stats:
        _show_log_stats(db_path)
        return
    p = Path(log_file)
    if not p.exists():
        console.print(
            f"[yellow]No log file found at {log_file}[/yellow]\n"
            "Logs appear after running [bold]nj search[/bold] "
            "or [bold]nj run[/bold]."
        )
        return
    lines = p.read_text(encoding="utf-8").splitlines()
    recent = lines[-last_n:] if len(lines) > last_n else lines
    for line in recent:
        if "error" in line.lower() or "failed" in line.lower():
            console.print(f"[red]{line}[/red]")
        elif "warning" in line.lower() or "warn" in line.lower():
            console.print(f"[yellow]{line}[/yellow]")
        else:
            console.print(f"[dim]{line}[/dim]")
    console.print(
        f"\n[dim]Showing last {len(recent)} of {len(lines)} log lines.[/dim]"
    )


def _show_log_stats(db_path: str) -> None:
    from rich import box
    from rich.table import Table

    from nj.db.repos.application_repo import ApplicationRepo
    from nj.db.repos.score_repo import ScoreRepo

    try:
        score_repo = ScoreRepo(db_path)
        app_repo = ApplicationRepo(db_path)
        failure_stats = score_repo.get_parse_failure_rate()
        apps = app_repo.get_applications()
        failed_apps = [
            a for a in apps
            if a.status.value in ("failed", "captcha_blocked", "bot_detected")
        ]
        table = Table(title="nj reliability stats", box=box.ROUNDED)
        table.add_column("Metric", width=30)
        table.add_column("Value", width=20, justify="right")

        table.add_row("Total jobs scored", str(failure_stats["total"]))
        table.add_row(
            "Parse failures",
            f"[{'red' if failure_stats['failures'] > 0 else 'green'}]"
            f"{failure_stats['failures']}[/]",
        )
        table.add_row(
            "Parse failure rate",
            f"[{'red' if failure_stats['rate_pct'] > 5 else 'green'}]"
            f"{failure_stats['rate_pct']}%[/]",
        )
        table.add_row("Total applications", str(len(apps)))
        table.add_row(
            "Failed applications",
            f"[{'red' if failed_apps else 'green'}]{len(failed_apps)}[/]",
        )
        console.print(table)

        if failure_stats["rate_pct"] > 5:
            console.print(
                "\n[yellow]Parse failure rate above 5% — "
                "consider hardening scoring prompt.[/yellow]\n"
                "Run [bold]nj logs --last 50[/bold] to review errors."
            )
    except Exception as e:
        console.print(f"[red]Stats unavailable:[/red] {e}")
