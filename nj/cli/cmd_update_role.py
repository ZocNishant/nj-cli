from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_update_role(config: Config, experience_id: str | None = None) -> None:
    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print("[red]cv/cv_base.json not found.[/red] Run [bold]nj init[/bold] first.")
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    experiences = [e for e in cv_base.get("experience", []) if isinstance(e, dict)]
    if not experiences:
        console.print("[yellow]No experience entries found in cv_base.json.[/yellow]")
        return

    if experience_id:
        target = next((e for e in experiences if e.get("id") == experience_id), None)
        if not target:
            console.print(f"[red]No experience with id '{experience_id}' found.[/red]")
            return
    elif len(experiences) == 1:
        target = experiences[0]
    else:
        console.print("\n[bold]Experience entries:[/bold]")
        for i, exp in enumerate(experiences, 1):
            title = exp.get("title", "Unknown")
            company = exp.get("company", "Unknown")
            exp_id = exp.get("id", "")
            console.print(
                f"  {i}. {title} @ {company}" + (f" [dim](id: {exp_id})[/dim]" if exp_id else "")
            )
        choice = Prompt.ask("Which entry to update? (number)", default="1")
        try:
            target = experiences[int(choice) - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid choice.[/red]")
            return

    title = target.get("title", "Role")
    company = target.get("company", "Company")

    console.print(
        Panel(
            f"Describe what you did / are doing as [bold]{title}[/bold] at [bold]{company}[/bold].\n"
            "[dim]Plain English is fine. Include any metrics or technologies if you have them.\n"
            "Example: 'Built a segmentation model for CT scans using PyTorch. "
            "Achieved 0.87 Dice score on the validation set.'[/dim]",
            title="nj update-role",
            border_style="cyan",
        )
    )

    description = console.input("\nDescribe your work: ").strip()
    if not description:
        console.print("[red]Description cannot be empty.[/red]")
        return

    console.print("\n[dim]Generating CV bullets...[/dim]")
    bullets = asyncio.run(_generate_bullets(description, title, company, config))

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
        target["bullets"] = bullets
        target["bullets_pending"] = False
        if target.get("status") == "incoming":
            target["status"] = "active"
        with open(cv_path, "w") as f:
            json.dump(cv_base, f, indent=2)
        console.print("[green]cv_base.json updated.[/green] Next nj run will use these bullets.")
    else:
        console.print("[dim]Discarded. Run again to retry.[/dim]")


async def _generate_bullets(
    description: str,
    title: str,
    company: str,
    config: Config,
) -> list[str]:
    import json as _json

    from nj.prompts.role_update_v1 import SYSTEM_PROMPT, build_user_prompt
    from nj.providers.base import LLMRequest
    from nj.providers.registry import get_provider

    try:
        provider = get_provider(config.llm, task="reasoning")
        request = LLMRequest(
            system=SYSTEM_PROMPT,
            user=build_user_prompt(description, title, company),
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
