from __future__ import annotations

import importlib
import random
import shlex
import sys
from datetime import datetime, UTC
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.prompt import Prompt
from rich.live import Live
from rich.table import Table
from rich import box

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

SHELL_COMMANDS = {
    "search":        "Scrape and score jobs",
    "run":           "Full pipeline — scrape, score, tailor, apply",
    "review":        "Review scored jobs interactively",
    "explain":       "Explain why a job scored the way it did",
    "diff":          "Show what changed in your tailored CV",
    "diagnose":      "Diagnose your CV — find root causes",
    "gaps":          "Skill gap analysis ranked by ROI",
    "frame":         "Reframe a project for a specific audience",
    "prep":          "Generate interview prep PDF",
    "tailor":        "Tailor CV for a specific job URL",
    "status":        "Application tracker dashboard",
    "calibrate":     "Tune score threshold",
    "label":         "Label jobs for calibration dataset",
    "quality":       "Run quality gate on tailored applications",
    "watch":         "Check Gmail for interview callbacks",
    "ml":            "ML models — sponsorship, salary, semantic",
    "graph":         "Career knowledge graph — visualize your career",
    "intel":         "H1B sponsorship intelligence — who sponsors ML/AI roles",
    "enrich":        "Full intelligence report for any job URL",
    "postmortem":    "Analyse why applications are failing",
    "update-cv":     "Update CV sections interactively",
    "update-intern": "Add internship bullets to CV",
    "logs":          "View logs or reliability stats",
    "config":        "View or edit configuration",
    "demo":          "Run interactive demo",
    "help":          "Show all commands",
    "clear":         "Clear the screen",
    "exit":          "Exit nj shell",
}

BOOT_MESSAGES = [
    "initializing career intelligence engine...",
    "loading anti-hallucination validator...",
    "warming up scoring models...",
    "calibrating visa detection...",
    "indexing job sources...",
    "mounting cv_base.json...",
    "connecting to provider...",
    "ready.",
]

BANNERS = [
    r"""
   ███╗   ██╗     ██╗
   ████╗  ██║     ██║
   ██╔██╗ ██║     ██║
   ██║╚██╗██║██   ██║
   ██║ ╚████║╚█████╔╝
   ╚═╝  ╚═══╝ ╚════╝ """,

    r"""
  ┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐
  │n││j││ ││c││a││r││e││e││r││ │
  └─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘""",

    r"""
   _  _     _
  | \| |   (_)
  | .` |    _
  |_|\_|   (_)
  career intelligence""",

    r"""
  ╔═╗╔═╗╦═╗╔═╗╔═╗╦═╗
  ║  ╠═╣╠╦╝║╣ ║╣ ╠╦╝
  ╚═╝╩ ╩╩╚═╚═╝╚═╝╩╚═
   ║║║╔═╗╦═╗╦╔═╔═╗
   ║║║║ ║╠╦╝╠╩╗╚═╗
   ╚╩╝╚═╝╩╚═╩ ╩╚═╝""",

    r"""
  +-+-+
  |n|j|
  +-+-+
  career operating system
  anti-hallucination by design""",

    r"""
  ░░░░░░░░░░░░░░░░░░░░
  ░░███╗░░██╗░░░░░██╗░
  ░████╗░██║░░░░░██╔╝░
  ░██╔██╗██║░░░░██╔╝░░
  ░██║╚████║██╗██╔╝░░░
  ░██║░╚███║╚████╔╝░░░
  ░╚═╝░░╚══╝░╚═══╝░░░░
  ░░░░░░░░░░░░░░░░░░░░""",
]

TAGLINES = [
    "never invents your experience.",
    "quality over quantity.",
    "your career. your data. your machine.",
    "anti-hallucination by design.",
    "signal over noise.",
    "OPT to offer. one command at a time.",
    "built for the ones who build things.",
    "explainable AI for technical careers.",
    "trust the score. question the threshold.",
    "find the right job. not just any job.",
]


def _boot_sequence() -> None:
    import time

    t_start = time.monotonic()
    console.print()
    for msg in BOOT_MESSAGES:
        console.print(f"  [dim cyan][ * ][/dim cyan] [dim]{msg}[/dim]")
        time.sleep(0.08)
    t_elapsed = round(time.monotonic() - t_start, 1)
    console.print(
        f"  [dim cyan][ ✓ ][/dim cyan] [dim]ready in {t_elapsed}s[/dim]"
    )
    console.print()


def _get_stats() -> dict:
    stats = {
        "jobs": 0,
        "scored": 0,
        "applied": 0,
        "interviews": 0,
    }
    try:
        db_path = "data/nj.db"
        if not Path(db_path).exists():
            return stats
        from nj.db.engine import get_engine
        from sqlalchemy import text

        engine = get_engine(db_path)
        with engine.connect() as conn:
            try:
                stats["jobs"] = (
                    conn.execute(
                        text("SELECT COUNT(*) FROM jobs")
                    ).scalar() or 0
                )
                stats["scored"] = (
                    conn.execute(
                        text("SELECT COUNT(*) FROM score_results")
                    ).scalar() or 0
                )
                stats["applied"] = (
                    conn.execute(
                        text(
                            "SELECT COUNT(*) FROM applications "
                            "WHERE status='submitted'"
                        )
                    ).scalar() or 0
                )
                stats["interviews"] = (
                    conn.execute(
                        text(
                            "SELECT COUNT(*) FROM applications "
                            "WHERE outcome='interview' "
                            "OR outcome='offer'"
                        )
                    ).scalar() or 0
                )
            except Exception:
                pass
    except Exception:
        pass
    return stats


def _render_splash(stats: dict, version: str) -> None:
    banner = random.choice(BANNERS)
    tagline = random.choice(TAGLINES)

    term_width = console.width or 80

    console.print(f"[bold cyan]{banner}[/bold cyan]")

    stats_parts = []
    if stats["jobs"] > 0:
        stats_parts.append(
            f"[dim]jobs tracked:[/dim]  "
            f"[cyan]{stats['jobs']}[/cyan]"
        )
    if stats["scored"] > 0:
        stats_parts.append(
            f"[dim]scored:[/dim]        "
            f"[cyan]{stats['scored']}[/cyan]"
        )
    if stats["applied"] > 0:
        stats_parts.append(
            f"[dim]applied:[/dim]       "
            f"[green]{stats['applied']}[/green]"
        )
    if stats["interviews"] > 0:
        stats_parts.append(
            f"[dim]interviews:[/dim]    "
            f"[bold green]{stats['interviews']}[/bold green]"
        )

    if stats_parts:
        console.print()
        for part in stats_parts:
            console.print(f"  {part}")

    console.print()
    console.print(f"  [dim italic]\"{tagline}\"[/dim italic]")
    console.print(
        f"  [dim]v{version} · "
        f"type [bold]help[/bold] to see commands · "
        f"[bold]exit[/bold] to quit[/dim]"
    )
    console.print()


def _show_help() -> None:
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        pad_edge=False,
        padding=(0, 2),
    )
    table.add_column("Command", style="bold cyan", width=18)
    table.add_column("Description", style="dim")

    sections = {
        "Intelligence": ["diagnose", "gaps", "explain", "diff", "frame", "graph", "intel", "ml"],
        "Job hunting":  ["search", "run", "review", "tailor", "quality"],
        "Applications": ["status", "calibrate", "label", "watch", "prep"],
        "CV management": ["update-cv", "update-intern"],
        "System": ["logs", "config", "demo", "help", "clear", "exit"],
    }

    for section, cmds in sections.items():
        table.add_row(f"[bold white]{section}[/bold white]", "")
        for cmd in cmds:
            desc = SHELL_COMMANDS.get(cmd, "")
            table.add_row(f"  {cmd}", desc)
        table.add_row("", "")

    console.print(table)
    console.print(
        "[dim]  Tip: commands accept same flags as CLI. "
        "Example: search --dry-run[/dim]\n"
    )


def _dispatch(command: str, args: list[str], config) -> bool:
    """Dispatch a shell command. Returns False to exit, True to continue."""
    if command in ("exit", "quit", "q"):
        return False

    if command == "clear":
        console.clear()
        return True

    if command == "help":
        _show_help()
        return True

    if command == "":
        return True

    COMMAND_MAP = {
        "search":        "nj.cli.cmd_search:run_search",
        "run":           "nj.cli.cmd_run:run_pipeline",
        "review":        "nj.cli.cmd_review:run_review",
        "explain":       "nj.cli.cmd_explain:run_explain",
        "diff":          "nj.cli.cmd_diff:run_diff",
        "diagnose":      "nj.cli.cmd_diagnose:run_diagnose",
        "gaps":          "nj.cli.cmd_gaps:run_gaps",
        "frame":         "nj.cli.cmd_frame:run_frame",
        "prep":          "nj.cli.cmd_prep:run_prep",
        "tailor":        "nj.cli.cmd_tailor:run_tailor",
        "status":        "nj.cli.cmd_status:run_status",
        "calibrate":     "nj.cli.cmd_calibrate:run_calibrate",
        "label":         "nj.cli.cmd_label:run_label",
        "quality":       "nj.cli.cmd_quality:run_quality_check",
        "watch":         "nj.cli.cmd_watch:run_watch",
        "ml":            "nj.cli.cmd_ml:run_ml",
        "graph":         "nj.cli.cmd_graph:run_graph",
        "intel":         "nj.cli.cmd_intel:run_intel",
        "enrich":        "nj.cli.cmd_enrich:run_enrich",
        "postmortem":    "nj.cli.cmd_postmortem:run_postmortem",
        "update-cv":     "nj.cli.cmd_update_cv:run_update_cv",
        "update-intern": "nj.cli.cmd_update_intern:run_update_intern",
        "logs":          "nj.cli.cmd_logs:run_logs",
        "demo":          "nj.cli.cmd_demo:run_demo",
    }

    if command not in COMMAND_MAP:
        console.print(
            f"  [red]Unknown command:[/red] {command}\n"
            f"  Type [bold]help[/bold] to see available commands."
        )
        return True

    module_path, func_name = COMMAND_MAP[command].split(":")
    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        if command == "tailor":
            url = args[0] if args else None
            if not url:
                console.print("  [red]Usage:[/red] tailor <url>")
                return True
            func(url=url, config=config, output_dir="output")
            return True

        if command == "explain":
            job_id = args[0] if args else None
            func(config=config, job_id=job_id)
            return True

        if command == "diff":
            job_id = args[0] if args else None
            func(config=config, job_id=job_id)
            return True

        if command == "prep":
            url = _get_flag(args, "--url")
            job_id = _get_flag(args, "--job-id") or (
                args[0]
                if args and not args[0].startswith("--")
                else None
            )
            last = "--last" in args
            func(config=config, url=url, job_id=job_id, last=last)
            return True

        if command == "frame":
            project_id = _get_flag(args, "--project") or _get_flag(
                args, "-p"
            )
            audience = _get_flag(args, "--audience") or _get_flag(
                args, "-a"
            )
            list_projects = "--list" in args or "-l" in args
            func(
                config=config,
                project_id=project_id,
                audience=audience,
                list_projects=list_projects,
            )
            return True

        if command == "search":
            dry_run = "--dry-run" in args
            func(config=config, dry_run=dry_run)
            return True

        if command == "run":
            dry_run = "--dry-run" in args
            silent = "--silent" in args
            func(config=config, dry_run=dry_run, silent=silent)
            return True

        if command == "calibrate":
            from_outcomes = "--from-outcomes" in args
            if from_outcomes:
                from nj.cli.cmd_calibrate import run_calibrate_from_outcomes

                run_calibrate_from_outcomes(config=config)
            else:
                func(config=config)
            return True

        if command == "logs":
            stats = "--stats" in args
            last_n = int(_get_flag(args, "--last") or 20)
            func(config=config, show_stats=stats, last_n=last_n)
            return True

        if command == "status":
            func(config=config)
            return True

        if command == "config":
            show = "--show" in args
            check = "--check-provider" in args
            from nj.cli.cmd_config import run_config

            run_config(config=config, show=show, check_provider=check)
            return True

        if command == "ml":
            sub = args[0] if args else "status"
            company = _get_flag(args, "--company") or _get_flag(args, "-c") or ""
            role_arg = _get_flag(args, "--role") or _get_flag(args, "-r") or ""
            state = _get_flag(args, "--state") or "CA"
            year_s = _get_flag(args, "--year")
            year = int(year_s) if year_s else 2024
            jid = _get_flag(args, "--job-id")
            from nj.cli.cmd_ml import run_ml

            run_ml(
                config=config,
                subcommand=sub,
                company=company,
                role=role_arg,
                state=state,
                year=year,
                job_id=jid,
            )
            return True

        if command == "graph":
            sub = args[0] if args else "stats"
            query_arg = args[1] if len(args) > 1 else ""
            target = _get_flag(args, "--target") or _get_flag(args, "-t") or ""
            from nj.cli.cmd_graph import run_graph

            run_graph(
                config=config,
                subcommand=sub,
                query=query_arg,
                target=target,
            )
            return True

        if command == "enrich":
            url_arg = args[0] if args else None
            no_score = "--no-score" in args
            from nj.cli.cmd_enrich import run_enrich
            run_enrich(config=config, url=url_arg, no_score=no_score)
            return True

        if command == "postmortem":
            min_apps = int(_get_flag(args, "--min") or 3)
            from nj.cli.cmd_postmortem import run_postmortem
            run_postmortem(config=config, min_applications=min_apps)
            return True

        if command == "intel":
            sub = args[0] if args else None
            # Collect remaining positional args (non-flag) as query
            query_parts = [
                a for i, a in enumerate(args[1:])
                if not a.startswith("-") and (
                    i == 0 or not args[i].startswith("-")
                )
            ]
            query_arg = " ".join(query_parts)
            state = _get_flag(args, "--state") or _get_flag(args, "-s") or ""
            year_str = _get_flag(args, "--year") or _get_flag(args, "-y") or "0"
            limit_str = _get_flag(args, "--limit") or _get_flag(args, "-n") or "20"
            try:
                year = int(year_str)
            except ValueError:
                year = 0
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 20
            func(
                subcommand=sub,
                query=query_arg,
                state=state,
                year=year,
                limit=limit,
            )
            return True

        func(config=config)

    except SystemExit:
        pass
    except KeyboardInterrupt:
        console.print("\n  [dim]Interrupted.[/dim]")
    except Exception as e:
        console.print(
            f"  [red]Error:[/red] {e}\n"
            f"  [dim]{type(e).__name__}[/dim]"
        )
        logger.warning(
            "shell_command_failed",
            command=command,
            error=str(e),
        )
    return True


def _parse_args(command: str, args: list[str]) -> dict:
    return {}


def _get_flag(args: list[str], flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(f"{flag}="):
            return arg.split("=", 1)[1]
    return None


def _get_prompt_text(config) -> str:
    provider = getattr(getattr(config, "llm", None), "provider", "?")
    return f"[bold cyan]nj[/bold cyan] [dim]({provider})[/dim] > "


def run_shell(version: str = "1.2.0") -> None:
    from nj.models.config import Config

    try:
        config = Config.load()
    except Exception:
        config = Config()

    _boot_sequence()
    stats = _get_stats()
    _render_splash(stats, version)

    try:
        while True:
            try:
                prompt_text = _get_prompt_text(config)
                raw = console.input(prompt_text)
                raw = raw.strip()

                if not raw:
                    continue

                try:
                    parts = shlex.split(raw)
                except ValueError:
                    parts = raw.split()

                command = parts[0].lower() if parts else ""
                args = parts[1:] if len(parts) > 1 else []

                should_continue = _dispatch(command, args, config)
                if not should_continue:
                    break

            except KeyboardInterrupt:
                console.print(
                    "\n  [dim]Use [bold]exit[/bold] to quit.[/dim]"
                )
                continue
            except EOFError:
                break

    except Exception as e:
        console.print(f"[red]Shell error:[/red] {e}")

    console.print()
    console.print(Panel(
        "[dim]session ended.[/dim]\n\n"
        "[dim]your data stays local. "
        "your cv stays yours.[/dim]",
        border_style="dim",
        width=40,
    ))
    console.print()
