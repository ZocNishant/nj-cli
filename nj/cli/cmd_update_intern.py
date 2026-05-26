from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_update_intern(config: Config) -> None:
    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print(
            "[red]cv/cv_base.json not found.[/red] " "Run [bold]nj init[/bold] first."
        )
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    moffitt = None
    for exp in cv_base.get("experience", []):
        if isinstance(exp, dict) and exp.get("id") == "moffitt_intern":
            moffitt = exp
            break

    if not moffitt:
        console.print(
            "[yellow]No Moffitt internship entry found "
            "in cv_base.json.[/yellow]\n"
            "Add an entry with id='moffitt_intern' first."
        )
        return

    console.print(
        Panel(
            "Describe what you're working on at Moffitt Cancer Center.\n"
            "[dim]Plain English is fine. Include any metrics or "
            "technologies if you have them.\n"
            "Example: 'I am building a segmentation model for CT scans "
            "using PyTorch and nnU-Net. The model achieves 0.87 Dice "
            "score on the validation set.'[/dim]",
            title="nj update-intern",
            border_style="cyan",
        )
    )

    description = console.input("\nDescribe your work: ").strip()
    if not description:
        console.print("[red]Description cannot be empty.[/red]")
        return

    console.print("\n[dim]Generating CV bullets...[/dim]")
    bullets = asyncio.run(_generate_bullets(description, config))

    if not bullets:
        console.print("[red]Failed to generate bullets.[/red] Try again.")
        return

    console.print(
        Panel(
            "\n".join(f"• {b}" for b in bullets),
            title="Generated bullets",
            border_style="green",
        )
    )

    if Confirm.ask("Save these bullets to cv_base.json?"):
        moffitt["bullets"] = bullets
        moffitt["bullets_pending"] = False
        moffitt["status"] = "active"
        with open(cv_path, "w") as f:
            json.dump(cv_base, f, indent=2)
        console.print(
            "[green]cv_base.json updated.[/green] "
            "Next nj run will use these bullets."
        )
    else:
        console.print("[dim]Discarded. Run again to retry.[/dim]")


async def _generate_bullets(description: str, config: Config) -> list[str]:
    import json as _json

    from nj.prompts.intern_update_v1 import SYSTEM_PROMPT, build_user_prompt
    from nj.providers.base import LLMRequest
    from nj.providers.registry import get_provider

    try:
        provider = get_provider(config.llm)
        request = LLMRequest(
            system=SYSTEM_PROMPT,
            user=build_user_prompt(description),
            max_tokens=400,
            temperature=0.3,
            response_format="json",
        )
        response = await provider.complete(request)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        bullets = _json.loads(raw)
        if isinstance(bullets, list):
            return [str(b) for b in bullets if b]
        return []
    except Exception as e:
        logger.error("bullet_generation_failed", error=str(e))
        return []
