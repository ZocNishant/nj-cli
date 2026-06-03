from __future__ import annotations

import importlib
import random
import readline
import shlex
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


class NJCompleter:
    """
    Tab completer for nj interactive shell.
    Completes:
    - Command names
    - Subcommands (intel sync, graph build, ml train...)
    - --flags for each command
    - File paths for URL arguments
    """

    SUBCOMMANDS = {
        "intel": ["sync", "top", "company", "role", "search", "stats"],
        "graph": ["build", "show", "stats", "skills", "companies", "path"],
        "ml": ["train", "predict", "salary", "semantic", "status"],
        "calibrate": ["--from-outcomes"],
        "logs": ["--stats", "--last"],
        "status": ["--no-trajectory"],
        "search": [
            "--dry-run",
            "--verbose",
            "--level junior",
            "--level mid",
            "--level senior",
            "--level staff",
            "--limit",
            "--all-langs",
            "--visa sponsor",
            "--visa any",
        ],
        "run": ["--dry-run", "--silent"],
        "diagnose": ["--no-pdf"],
        "gaps": ["--top"],
        "frame": [
            "--list",
            "--audience production_ml",
            "--audience research_lab",
            "--audience healthtech_startup",
            "--audience big_tech",
            "--audience early_stage_startup",
            "--audience custom",
        ],
        "prep": ["--last", "--job-id", "--url"],
        "explain": ["--top"],
        "diff": [
            "--section skills",
            "--section experience",
            "--section projects",
            "--section summary",
        ],
        "enrich": ["--no-score"],
        "update-cv": [
            "--show",
            "--section summary",
            "--section skills",
            "--section personal",
            "--section research_interests",
        ],
        "config": ["--show", "--check-provider"],
        "tailor": [],
        "review": [],
        "label": [],
        "quality": [],
        "watch": ["--setup", "--days"],
        "init": ["--force"],
        "update-role": [],
        "update-intern": [],
        "postmortem": [],
        "demo": [],
        "manual": list(
            {
                "search",
                "enrich",
                "explain",
                "diagnose",
                "gaps",
                "frame",
                "diff",
                "postmortem",
                "intel",
                "graph",
                "ml",
                "prep",
                "review",
                "status",
                "calibrate",
                "watch",
                "tailor",
                "update-cv",
                "update-role",
                "update-intern",
                "init",
                "run",
                "demo",
                "logs",
                "config",
                "quality",
                "label",
                "manual",
            }
        ),
        "help": [],
        "clear": [],
        "exit": [],
        "quit": [],
    }

    def __init__(self, commands: list[str]):
        self.commands = sorted(commands)
        self.matches: list[str] = []

    def complete(self, text: str, state: int) -> str | None:
        if state == 0:
            self.matches = self._get_matches(text)
        try:
            return self.matches[state]
        except IndexError:
            return None

    def _get_matches(self, text: str) -> list[str]:
        line = readline.get_line_buffer()
        parts = line.split()

        if len(parts) == 0 or (len(parts) == 1 and not line.endswith(" ")):
            return [c + " " for c in self.commands if c.startswith(text)]

        first_word = parts[0].lower()
        if first_word in self.SUBCOMMANDS:
            subs = self.SUBCOMMANDS[first_word]
            if len(parts) == 1 and line.endswith(" "):
                return subs
            elif len(parts) >= 2:
                current = parts[-1] if not line.endswith(" ") else ""
                return [s for s in subs if s.startswith(current)]

        return []


class LiveStatus:
    """Shows animated status during long operations."""

    SPINNERS = ["dots", "dots2", "dots3", "line", "pipe", "simpleDots"]

    def __init__(self, title: str = "") -> None:
        self.title = title
        self.messages: list[str] = []
        self.done = False
        self._live = None
        self._spinner_name = random.choice(self.SPINNERS)

    def update(self, message: str) -> None:
        self.messages.append(message)
        if len(self.messages) > 6:
            self.messages = self.messages[-6:]

    def _render(self) -> Text:
        text = Text()
        text.append(f"\n  {self.title}\n\n", style="bold cyan")
        for i, msg in enumerate(self.messages):
            if i == len(self.messages) - 1:
                text.append(f"  [cyan]►[/cyan] {msg}\n")
            else:
                text.append(f"  [dim]✓ {msg}[/dim]\n")
        return text


def _setup_readline() -> None:
    try:
        import gnureadline as _rl
    except ImportError:
        import readline as _rl  # type: ignore[no-redef]

    try:
        completer_instance = NJCompleter(list(SHELL_COMMANDS.keys()))
        _rl.set_completer(completer_instance.complete)
        _rl.set_completer_delims(" \t\n")
        _rl.parse_and_bind("tab: complete")
        _rl.parse_and_bind('"\\e[A": history-search-backward')
        _rl.parse_and_bind('"\\e[B": history-search-forward')

        history_path = Path.home() / ".nj_history"
        if history_path.exists():
            _rl.read_history_file(str(history_path))
        _rl.set_history_length(500)
    except Exception as e:
        logger.debug("readline_setup_failed", error=str(e))


SHELL_COMMANDS = {
    "search": "Scrape and score jobs",
    "run": "Full pipeline — scrape, score, tailor, apply",
    "review": "Review scored jobs interactively",
    "explain": "Explain why a job scored the way it did",
    "diff": "Show what changed in your tailored CV",
    "diagnose": "Diagnose your CV — find root causes",
    "gaps": "Skill gap analysis ranked by ROI",
    "frame": "Reframe a project for a specific audience",
    "prep": "Generate interview prep PDF",
    "tailor": "Tailor CV for a specific job URL",
    "status": "Application tracker dashboard",
    "calibrate": "Tune score threshold",
    "label": "Label jobs for calibration dataset",
    "quality": "Run quality gate on tailored applications",
    "watch": "Check Gmail for interview callbacks",
    "ml": "ML models — sponsorship, salary, semantic",
    "graph": "Career knowledge graph — visualize your career",
    "intel": "H1B sponsorship intelligence — who sponsors ML/AI roles",
    "enrich": "Full intelligence report for any job URL",
    "postmortem": "Analyse why applications are failing",
    "init": "First-time setup wizard",
    "update-cv": "Update CV sections interactively",
    "update-role": "Add any new role/job to your CV",
    "update-intern": "Alias for update-role (backward-compatible)",
    "logs": "View logs or reliability stats",
    "config": "View or edit configuration",
    "manual": "Full command reference with examples",
    "demo": "Run interactive demo",
    "help": "Show all commands",
    "clear": "Clear the screen",
    "exit": "Exit nj shell",
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


def _matrix_flash() -> None:
    """Brief matrix-style effect on boot."""
    if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
        return
    chars = "01アイウエオカキクケコサシスセソ"
    width = min(console.width or 60, 60)

    for _ in range(3):
        line = "".join(random.choice(chars) for _ in range(width))
        console.print(f"[bold green dim]{line}[/bold green dim]")
        time.sleep(0.04)

    time.sleep(0.1)


def _boot_sequence() -> None:
    _matrix_flash()

    messages = [
        ("initializing career intelligence engine", 0.06),
        ("loading anti-hallucination validator", 0.05),
        ("mounting cv_base.json", 0.05),
        ("connecting to provider", 0.05),
        ("warming up scoring models", 0.05),
        ("indexing job sources", 0.04),
        ("calibrating visa detection", 0.04),
        ("ready", 0.03),
    ]

    console.print()
    for msg, delay in messages:
        console.print(f"  [dim cyan][ * ][/dim cyan] [dim]{msg}[/dim]")
        time.sleep(delay)
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
                    conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar() or 0
                )
                stats["scored"] = (
                    conn.execute(text("SELECT COUNT(*) FROM score_results")).scalar()
                    or 0
                )
                stats["applied"] = (
                    conn.execute(
                        text(
                            "SELECT COUNT(*) FROM applications "
                            "WHERE status='submitted'"
                        )
                    ).scalar()
                    or 0
                )
                stats["interviews"] = (
                    conn.execute(
                        text(
                            "SELECT COUNT(*) FROM applications "
                            "WHERE outcome='interview' "
                            "OR outcome='offer'"
                        )
                    ).scalar()
                    or 0
                )
            except Exception:
                pass
    except Exception:
        pass
    return stats


def _render_splash(stats: dict, version: str) -> None:
    banner = random.choice(BANNERS)
    tagline = random.choice(TAGLINES)

    lines = banner.strip().split("\n")
    colors = ["bold cyan", "cyan", "bold cyan", "cyan", "bold cyan", "cyan"]
    for i, line in enumerate(lines):
        color = colors[i % len(colors)]
        console.print(f"[{color}]{line}[/{color}]")

    console.print()

    if stats.get("jobs", 0) > 0:
        stat_parts = []
        if stats["jobs"] > 0:
            stat_parts.append(
                f"[cyan]◆[/cyan] [bold]{stats['jobs']}[/bold] [dim]jobs[/dim]"
            )
        if stats.get("scored", 0) > 0:
            stat_parts.append(
                f"[cyan]◆[/cyan] [bold]{stats['scored']}[/bold] [dim]scored[/dim]"
            )
        if stats.get("applied", 0) > 0:
            stat_parts.append(
                f"[green]◆[/green] [bold]{stats['applied']}[/bold] [dim]applied[/dim]"
            )
        if stats.get("interviews", 0) > 0:
            stat_parts.append(
                f"[bold green]◆[/bold green] [bold]{stats['interviews']}[/bold] [dim]interviews[/dim]"
            )
        if stat_parts:
            console.print("  " + "  ".join(stat_parts))

    console.print()
    console.print(f'  [dim italic]"{tagline}"[/dim italic]')
    console.print(
        f"\n  [dim]v{version}  ·  "
        f"Tab complete  ·  ↑↓ history  ·  "
        f"[bold]help[/bold] for commands[/dim]"
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
        "Intelligence": [
            "diagnose",
            "gaps",
            "explain",
            "diff",
            "frame",
            "graph",
            "intel",
            "ml",
        ],
        "Job hunting": ["search", "run", "review", "tailor", "quality"],
        "Applications": ["status", "calibrate", "label", "watch", "prep"],
        "CV management": ["update-cv", "update-role"],
        "System": ["logs", "config", "manual", "demo", "help", "clear", "exit"],
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
        "search": "nj.cli.cmd_search:run_search",
        "run": "nj.cli.cmd_run:run_pipeline",
        "review": "nj.cli.cmd_review:run_review",
        "explain": "nj.cli.cmd_explain:run_explain",
        "diff": "nj.cli.cmd_diff:run_diff",
        "diagnose": "nj.cli.cmd_diagnose:run_diagnose",
        "gaps": "nj.cli.cmd_gaps:run_gaps",
        "frame": "nj.cli.cmd_frame:run_frame",
        "prep": "nj.cli.cmd_prep:run_prep",
        "tailor": "nj.cli.cmd_tailor:run_tailor",
        "status": "nj.cli.cmd_status:run_status",
        "calibrate": "nj.cli.cmd_calibrate:run_calibrate",
        "label": "nj.cli.cmd_label:run_label",
        "quality": "nj.cli.cmd_quality:run_quality_check",
        "watch": "nj.cli.cmd_watch:run_watch",
        "ml": "nj.cli.cmd_ml:run_ml",
        "graph": "nj.cli.cmd_graph:run_graph",
        "intel": "nj.cli.cmd_intel:run_intel",
        "enrich": "nj.cli.cmd_enrich:run_enrich",
        "postmortem": "nj.cli.cmd_postmortem:run_postmortem",
        "update-cv": "nj.cli.cmd_update_cv:run_update_cv",
        "init": "nj.cli.cmd_init:run_init",
        "update-role": "nj.cli.cmd_update_role:run_update_role",
        "update-intern": "nj.cli.cmd_update_intern:run_update_intern",
        "logs": "nj.cli.cmd_logs:run_logs",
        "demo": "nj.cli.cmd_demo:run_demo",
        "manual": "nj.cli.cmd_help_full:run_manual",
    }

    _print_command_header(command)

    if command == "config":
        show = "--show" in args
        check = "--check-provider" in args
        from nj.cli.cmd_config import run_config

        run_config(config=config, show=show, check_provider=check)
        return True

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
            _show_success(command)
            return True

        if command == "explain":
            job_id = args[0] if args else None
            func(config=config, job_id=job_id)
            _show_success(command)
            return True

        if command == "diff":
            job_id = args[0] if args else None
            func(config=config, job_id=job_id)
            _show_success(command)
            return True

        if command == "prep":
            url = _get_flag(args, "--url")
            job_id = _get_flag(args, "--job-id") or (
                args[0] if args and not args[0].startswith("--") else None
            )
            last = "--last" in args
            func(config=config, url=url, job_id=job_id, last=last)
            _show_success(command)
            return True

        if command == "frame":
            project_id = _get_flag(args, "--project") or _get_flag(args, "-p")
            audience = _get_flag(args, "--audience") or _get_flag(args, "-a")
            list_projects = "--list" in args or "-l" in args
            func(
                config=config,
                project_id=project_id,
                audience=audience,
                list_projects=list_projects,
            )
            _show_success(command)
            return True

        if command == "search":
            dry_run = "--dry-run" in args
            level_arg = _get_flag(args, "--level") or _get_flag(args, "-l")
            limit_s = _get_flag(args, "--limit") or _get_flag(args, "-n")
            limit = int(limit_s) if limit_s else 50
            all_langs = "--all-langs" in args
            visa_mode = _get_flag(args, "--visa") or "any"
            func(
                config=config,
                dry_run=dry_run,
                level=level_arg,
                limit=limit,
                all_langs=all_langs,
                visa_mode=visa_mode,
            )
            _show_success(command)
            return True

        if command == "run":
            dry_run = "--dry-run" in args
            silent = "--silent" in args
            func(config=config, dry_run=dry_run, silent=silent)
            _show_success(command)
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
            _show_success(command)
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
            _show_success(command)
            return True

        if command == "enrich":
            url_arg = args[0] if args else None
            no_score = "--no-score" in args
            from nj.cli.cmd_enrich import run_enrich

            run_enrich(config=config, url=url_arg, no_score=no_score)
            _show_success(command)
            return True

        if command == "postmortem":
            min_apps = int(_get_flag(args, "--min") or 3)
            from nj.cli.cmd_postmortem import run_postmortem

            run_postmortem(config=config, min_applications=min_apps)
            _show_success(command)
            return True

        if command == "manual":
            cmd_arg = args[0] if args else None
            from nj.cli.cmd_help_full import run_manual

            run_manual(command=cmd_arg)
            return True

        if command == "intel":
            sub = args[0] if args else None
            # Collect remaining positional args (non-flag) as query
            query_parts = [
                a
                for i, a in enumerate(args[1:])
                if not a.startswith("-") and (i == 0 or not args[i].startswith("-"))
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
            _show_success(command)
            return True

        if command == "init":
            from nj.cli.cmd_init import run_init

            force = "--force" in args
            run_init(force=force)
            return True

        if command == "update-role":
            from nj.cli.cmd_update_role import run_update_role

            run_update_role(config=config)
            return True

        func(config=config)
        if command in _HEAVY_COMMANDS:
            _show_success(command)

    except SystemExit:
        pass
    except KeyboardInterrupt:
        console.print("\n  [dim]Interrupted.[/dim]")
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}\n" f"  [dim]{type(e).__name__}[/dim]")
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


_HEAVY_COMMANDS: frozenset[str] = frozenset(
    {
        "search",
        "run",
        "diagnose",
        "gaps",
        "frame",
        "prep",
        "tailor",
        "enrich",
        "graph",
        "ml",
        "intel",
        "watch",
        "postmortem",
        "diff",
        "explain",
    }
)

_SUCCESS_MESSAGES: dict[str, str] = {
    "search": "search complete",
    "diagnose": "diagnosis ready",
    "gaps": "gap analysis done",
    "graph": "graph updated",
    "ml": "models ready",
    "intel": "intel loaded",
    "enrich": "enrichment done",
    "prep": "prep PDF ready",
    "tailor": "CV tailored",
}


def _print_command_header(command: str) -> None:
    """Print a subtle separator before command output."""
    timestamp = time.strftime("%H:%M:%S")
    console.print(
        f"\n[dim]─── {command} "
        f"{'─' * max(0, 40 - len(command))} "
        f"{timestamp} ───[/dim]"
    )


def _show_success(command: str) -> None:
    """Brief success indicator."""
    msg = _SUCCESS_MESSAGES.get(command, "done")
    console.print(f"\n  [dim green]✓ {msg}[/dim green]\n")


def _get_prompt_text(config, stats: dict | None = None) -> str:
    provider = getattr(getattr(config, "llm", None), "provider", "claude")
    if stats and stats.get("jobs", 0) > 0:
        jobs = stats["jobs"]
        applied = stats.get("applied", 0)
        state = f"{jobs}j·{applied}a" if applied > 0 else f"{jobs}j"
        return (
            f"[bold cyan]nj[/bold cyan]"
            f"[dim]({provider})[/dim]"
            f"[dim cyan][{state}][/dim cyan] "
            f"[bold]>[/bold] "
        )
    return f"[bold cyan]nj[/bold cyan]" f"[dim]({provider})[/dim] " f"[bold]>[/bold] "


def _get_prompt_plain(config, stats: dict | None = None) -> str:
    provider = getattr(getattr(config, "llm", None), "provider", "claude")
    if stats and stats.get("jobs", 0) > 0:
        jobs = stats["jobs"]
        applied = stats.get("applied", 0)
        state = f"{jobs}j·{applied}a" if applied > 0 else f"{jobs}j"
        return f"nj({provider})[{state}] > "
    return f"nj({provider}) > "


def _get_input(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    return line.rstrip("\n")


def run_shell(version: str = "1.2.0") -> None:
    db_path = "data/nj.db"
    try:
        from nj.db.engine import init_db

        init_db(db_path)
    except Exception:
        pass

    try:
        from nj.utils.logger import setup_logger

        setup_logger()
    except Exception:
        pass

    from nj.models.config import Config

    try:
        config = Config.load()
    except Exception:
        config = Config()

    _setup_readline()

    _boot_sequence()
    stats = _get_stats()
    _render_splash(stats, version)

    try:
        while True:
            try:
                stats = _get_stats()
                prompt_plain = _get_prompt_plain(config, stats)
                raw = _get_input(prompt_plain)
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
                print()  # blank line between command output and next prompt

            except KeyboardInterrupt:
                console.print("\n  [dim]Use [bold]exit[/bold] to quit.[/dim]")
                continue
            except EOFError:
                break

    except Exception as e:
        console.print(f"[red]Shell error:[/red] {e}")

    try:
        try:
            import gnureadline as _rl_write
        except ImportError:
            import readline as _rl_write  # type: ignore[no-redef]
        _rl_write.write_history_file(str(Path.home() / ".nj_history"))
    except Exception:
        pass

    console.print()
    console.print(
        Panel(
            "[dim]session ended.[/dim]\n\n"
            "[dim]your data stays local. "
            "your cv stays yours.[/dim]",
            border_style="dim",
            width=40,
        )
    )
    console.print()
