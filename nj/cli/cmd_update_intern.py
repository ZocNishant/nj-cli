from __future__ import annotations

from pathlib import Path

from rich.console import Console

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_update_intern(config: Config) -> None:
    """Backward-compatible alias for update-role."""
    if not Path("cv/cv_base.json").exists():
        console.print("[red]cv/cv_base.json not found.[/red] Run [bold]nj init[/bold] first.")
        return
    from nj.cli.cmd_update_role import run_update_role

    run_update_role(config)
