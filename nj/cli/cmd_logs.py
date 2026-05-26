from __future__ import annotations

from pathlib import Path

from rich.console import Console

from nj.models.config import Config

console = Console()


def run_logs(
    config: Config,
    last_n: int = 20,
    log_file: str = "logs/nj.log",
) -> None:
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
        f"\n[dim]Showing last {len(recent)} of " f"{len(lines)} log lines.[/dim]"
    )
