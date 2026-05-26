from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

from nj.models.config import Config

console = Console()


def run_config(
    config: Config,
    config_path: str = "config.yaml",
    show: bool = False,
) -> None:
    p = Path(config_path)
    if not p.exists():
        console.print(
            f"[yellow]{config_path} not found.[/yellow] "
            "Run [bold]nj init[/bold] first."
        )
        return
    if show:
        content = p.read_text()
        syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
        return
    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run([editor, config_path])
    except FileNotFoundError:
        console.print(
            f"[yellow]Editor '{editor}' not found.[/yellow]\n"
            f"Set $EDITOR or edit {config_path} manually."
        )
