from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel as RPanel
from rich.syntax import Syntax

from nj.models.config import Config

console = Console()


async def _check_provider_async(config: Config) -> dict:
    import time

    from nj.providers.base import LLMRequest
    from nj.providers.registry import get_provider

    provider = get_provider(config.llm)
    request = LLMRequest(
        system="You are a test assistant.",
        user="Reply with exactly one word: READY",
        max_tokens=10,
        temperature=0.0,
        response_format="text",
    )
    start = time.monotonic()
    response = await provider.complete(request)
    latency = int((time.monotonic() - start) * 1000)
    return {
        "provider": response.provider,
        "model": response.model,
        "response": response.content.strip(),
        "latency_ms": latency,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }


def run_check_provider(config: Config) -> None:
    import asyncio

    console.print(
        f"[dim]Testing provider: [bold]{config.llm.provider}[/bold]...[/dim]"
    )
    try:
        result = asyncio.run(_check_provider_async(config))
        console.print(
            RPanel(
                f"[green]✓ Connected[/green]\n\n"
                f"Provider:  [bold]{result['provider']}[/bold]\n"
                f"Model:     [bold]{result['model']}[/bold]\n"
                f"Response:  {result['response']}\n"
                f"Latency:   {result['latency_ms']}ms\n"
                f"Tokens:    "
                f"{result['input_tokens']} in / "
                f"{result['output_tokens']} out",
                title="Provider check",
                border_style="green",
            )
        )
    except ImportError as e:
        console.print(f"[red]Missing dependency:[/red] {e}")
    except Exception as e:
        console.print(
            f"[red]Provider check failed:[/red] {e}\n"
            f"[dim]Check your API key and provider config.[/dim]"
        )


def run_config(
    config: Config,
    config_path: str = "config.yaml",
    show: bool = False,
    check_provider: bool = False,
) -> None:
    if check_provider:
        run_check_provider(config)
        return
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
