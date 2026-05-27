from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

EDITABLE_SECTIONS = {
    "summary": "3-line professional summary paragraph",
    "skills": "Technical skills by category",
    "research_interests": "Research interest areas",
    "soft_skills": "Soft skills list",
    "personal": "Personal info (name, email, phone, location)",
}


def run_update_cv(
    config: Config,
    section: str | None = None,
    show: bool = False,
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

    if show:
        _show_cv_sections(cv_base)
        return

    if not section:
        _show_cv_sections(cv_base)
        section = Prompt.ask(
            "\nWhich section to update?",
            choices=list(EDITABLE_SECTIONS.keys()),
        )

    if section not in EDITABLE_SECTIONS:
        console.print(
            f"[red]Unknown section: {section}[/red]\n"
            f"Available: {', '.join(EDITABLE_SECTIONS.keys())}"
        )
        return

    _update_section(cv_base, section, cv_path)


def _show_cv_sections(cv_base: dict) -> None:
    console.print("\n[bold]cv_base.json — current sections:[/bold]\n")
    for key, description in EDITABLE_SECTIONS.items():
        value = cv_base.get(key, "")
        if isinstance(value, list):
            preview = ", ".join(str(v) for v in value[:3])
            if len(value) > 3:
                preview += f" ... (+{len(value) - 3} more)"
        elif isinstance(value, dict):
            parts = []
            for k, v in list(value.items())[:3]:
                if isinstance(v, list):
                    parts.append(", ".join(str(x) for x in v[:3]))
                else:
                    parts.append(f"{k}: {v}")
            preview = ", ".join(parts)
        else:
            preview = str(value)[:80] if value else "[dim]empty[/dim]"
        console.print(
            f"  [bold cyan]{key:<22}[/bold cyan] "
            f"[dim]{description}[/dim]\n"
            f"  {'':22} {preview}\n"
        )


def _update_section(cv_base: dict, section: str, cv_path: Path) -> None:
    current = cv_base.get(section, "")
    console.print(f"\n[bold]Current {section}:[/bold]")

    if isinstance(current, str):
        console.print(f"[dim]{current if current else '(empty)'}[/dim]\n")
        new_value = Prompt.ask(f"New {section}")
        cv_base[section] = new_value

    elif isinstance(current, list):
        console.print(
            "[dim]"
            + "\n".join(f"  • {item}" for item in current)
            + "[/dim]\n"
        )
        console.print(
            "Enter new values (comma-separated) or press Enter to keep current:"
        )
        raw = Prompt.ask(f"New {section}", default="")
        if raw.strip():
            cv_base[section] = [v.strip() for v in raw.split(",") if v.strip()]

    elif isinstance(current, dict) and section == "personal":
        for field in ["name", "email", "phone", "location", "linkedin", "github"]:
            old_val = current.get(field, "")
            new_val = Prompt.ask(f"  {field}", default=old_val)
            if new_val != old_val:
                current[field] = new_val
        cv_base[section] = current

    elif isinstance(current, dict):
        console.print(Syntax(json.dumps(current, indent=2), "json", theme="monokai"))
        console.print(
            "[dim]Edit cv/cv_base.json directly for complex section updates.[/dim]"
        )
        return

    console.print(f"\n[bold]Updated {section}:[/bold] {cv_base.get(section)}")
    if Confirm.ask("Save?", default=True):
        with open(cv_path, "w") as f:
            json.dump(cv_base, f, indent=2)
        console.print(f"[green]✓ {section} updated in cv_base.json[/green]")
    else:
        console.print("[dim]Discarded.[/dim]")
