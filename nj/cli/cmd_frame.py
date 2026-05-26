from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from nj.models.config import Config
from nj.prompts.frame_v1 import AUDIENCE_PROFILES
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_frame(
    config: Config,
    project_id: str | None = None,
    audience: str | None = None,
    role_description: str = "",
    list_projects: bool = False,
) -> None:
    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print(
            "[red]cv/cv_base.json not found.[/red] "
            "Run [bold]nj init[/bold] first."
        )
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    projects = cv_base.get("projects", [])
    if not projects:
        console.print("[yellow]No projects found in cv_base.json.[/yellow]")
        return

    if list_projects:
        _list_projects(projects)
        return

    project = _select_project(projects, project_id)
    if not project:
        return

    if not audience:
        audience = _select_audience()

    if audience == "custom" and not role_description:
        role_description = Prompt.ask("Describe the role/audience in a few sentences")

    from nj.prompts.frame_v1 import SYSTEM_PROMPT, build_user_prompt
    from nj.providers.base import LLMRequest
    from nj.providers.registry import get_provider
    from nj.tailoring.anti_hallucination import validate_tailored_cv

    provider = get_provider(config.llm)

    console.print(
        f"\n[dim]Reframing [bold]{project.get('name', '')}[/bold] "
        f"for [bold]{audience}[/bold]...[/dim]\n"
    )

    try:
        result = asyncio.run(
            _generate_framing(
                project,
                audience,
                role_description,
                provider,
                SYSTEM_PROMPT,
                build_user_prompt,
                LLMRequest,
            )
        )
    except Exception as e:
        console.print(f"[red]Framing failed:[/red] {e}")
        return

    original_text = {"project": project}
    reframed_text = {"bullets": result.get("reframed_bullets", [])}
    is_valid, violations = validate_tailored_cv(original_text, reframed_text)
    if not is_valid:
        console.print(
            "[yellow]Warning: potential invented content detected:[/yellow]"
        )
        for v in violations[:3]:
            console.print(f"  [yellow]• {v}[/yellow]")
        console.print("[dim]Review reframed bullets carefully.[/dim]\n")

    _display_framing(project, result, audience)
    _offer_save(result, project, cv_base, cv_path, audience)


async def _generate_framing(
    project,
    audience,
    role_description,
    provider,
    system_prompt,
    build_user_prompt_fn,
    LLMRequest,
) -> dict:
    user_prompt = build_user_prompt_fn(
        project=project,
        audience=audience,
        role_description=role_description,
    )
    request = LLMRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=1500,
        temperature=0.4,
        response_format="json",
    )
    for attempt in range(1, 3):
        try:
            response = await provider.complete(request)
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            return json.loads(raw)
        except Exception as e:
            logger.warning("frame_attempt_failed", attempt=attempt, error=str(e))
            if attempt == 2:
                raise
    return {}


def _list_projects(projects: list) -> None:
    console.print("\n[bold]Projects in cv_base.json:[/bold]\n")
    for p in projects:
        anchor = " [bold cyan][anchor][/bold cyan]" if p.get("anchor") else ""
        console.print(
            f"  [bold]{p.get('id', '')}[/bold]{anchor} — "
            f"{p.get('name', '')} "
            f"[dim]({', '.join(p.get('tech', [])[:3])})[/dim]"
        )
    console.print(
        "\nUse [bold]nj frame --project PROJECT_ID[/bold] "
        "to frame a specific project."
    )


def _select_project(projects: list, project_id: str | None) -> dict | None:
    if project_id:
        match = next((p for p in projects if p.get("id") == project_id), None)
        if not match:
            console.print(
                f"[red]Project '{project_id}' not found.[/red]\n"
                "Run [bold]nj frame --list[/bold] to see projects."
            )
            return None
        return match

    anchor = next((p for p in projects if p.get("anchor")), None)
    if anchor:
        console.print(
            f"[dim]No project specified — using anchor project: "
            f"[bold]{anchor.get('name', '')}[/bold][/dim]"
        )
        return anchor

    return projects[0]


def _select_audience() -> str:
    console.print("\n[bold]Select target audience:[/bold]\n")
    audience_descriptions = {
        "production_ml": "Production ML team — cares about scale, deployment, MLOps",
        "research_lab": "Research lab — cares about methodology, rigor, novelty",
        "healthtech_startup": "Healthtech startup — cares about clinical relevance, domain expertise",
        "big_tech": "Big tech — cares about scale, systems, ownership",
        "early_stage_startup": "Early startup — cares about breadth, speed, ownership",
        "custom": "Custom — describe the role yourself",
    }
    for i, (key, desc) in enumerate(audience_descriptions.items(), 1):
        console.print(f"  [bold]{i}.[/bold] {desc}")

    choice = Prompt.ask("\nEnter number or audience name", default="1")
    try:
        idx = int(choice) - 1
        return list(audience_descriptions.keys())[idx]
    except (ValueError, IndexError):
        if choice in AUDIENCE_PROFILES:
            return choice
        return "production_ml"


def _display_framing(project: dict, result: dict, audience: str) -> None:
    name = project.get("name", "Project")
    console.print(
        Panel(
            f"[bold]{name}[/bold] → [cyan]{audience}[/cyan]\n\n"
            f"[bold]Framing angle:[/bold] {result.get('framing_angle', '')}\n\n"
            f"[bold]Reframed summary:[/bold]\n{result.get('reframed_summary', '')}",
            title="Framing result",
            border_style="cyan",
        )
    )

    bullets = result.get("reframed_bullets", [])
    if bullets:
        console.print("\n[bold]Reframed bullets:[/bold]")
        for b in bullets:
            console.print(f"  [green]•[/green] {b}")

    what_changed = result.get("what_changed", "")
    if what_changed:
        console.print(
            Panel(what_changed, title="What changed and why", border_style="dim")
        )

    verbal = result.get("what_to_emphasize_verbally", "")
    if verbal:
        console.print(
            Panel(
                f"[italic]{verbal}[/italic]",
                title="What to say in the interview (beyond the CV)",
                border_style="green",
            )
        )

    warnings = result.get("warnings", [])
    if warnings:
        console.print("\n[bold yellow]Fit warnings:[/bold yellow]")
        for w in warnings:
            console.print(f"  [yellow]•[/yellow] {w}")


def _offer_save(
    result: dict,
    project: dict,
    cv_base: dict,
    cv_path: Path,
    audience: str,
) -> None:
    bullets = result.get("reframed_bullets", [])
    if not bullets:
        return

    console.print(
        "\n[dim]Save reframed bullets to cv_base.json? "
        "This creates a variant — your original is preserved.[/dim]"
    )
    from rich.prompt import Confirm

    if Confirm.ask(
        f"Save as '{project.get('id', '')}_{audience}' variant?",
        default=False,
    ):
        variant_id = f"{project.get('id', 'project')}_{audience}"
        existing = cv_base.get("projects", [])
        variant = {
            **project,
            "id": variant_id,
            "name": f"{project.get('name', '')} ({audience})",
            "bullets": bullets,
            "anchor": False,
            "is_variant": True,
            "variant_of": project.get("id", ""),
            "variant_audience": audience,
        }
        existing_ids = [p.get("id") for p in existing]
        if variant_id in existing_ids:
            existing = [
                variant if p.get("id") == variant_id else p for p in existing
            ]
        else:
            existing.append(variant)
        cv_base["projects"] = existing
        with open(cv_path, "w") as f:
            json.dump(cv_base, f, indent=2)
        console.print(
            f"[green]Saved variant '{variant_id}' to cv_base.json[/green]"
        )
