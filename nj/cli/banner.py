import random
import sys

from rich.console import Console
from rich.text import Text

console = Console()

BANNERS = [
    r"""
   ███╗   ██╗     ██╗
   ████╗  ██║     ██║
   ██╔██╗ ██║     ██║
   ██║╚██╗██║██   ██║
   ██║ ╚████║╚█████╔╝
   ╚═╝  ╚═══╝ ╚════╝ """,
    r"""
    ___ ___
   |   |   |
   | n | j |
   |___|___|
   career intelligence""",
    r"""
   ┌──────────────────┐
   │  nj :: v{version}  │
   │  career engine   │
   └──────────────────┘""",
    r"""
    ███╗
   ██╔██╗  nj
   ██║╚██╗ career
   ██║ ╚██╗operating
   ╚═╝  ╚═╝system""",
    r"""
   ╔╗╔      ╦
   ║║║      ║
   ╝╚╝ ██╗  ╩
       ╚═╝     """,
    r"""
  ______  __
 /      \/  |
 $$$$$$  $$ |
 $$ |  $$ $$ |
 $$ \__$$ $$ |
 $$    $$ $$ |
  $$$$$$  $$/
   """,
    r"""
  ┌─┐
  │n│  job hunter
  │j│  career os
  └─┘  v{version}""",
    r"""
   _  _
  | \| |
  | .` |_ __
  |_|\_(_)
  career ops""",
]

TAGLINES = [
    "quality over quantity.",
    "trust the score. question the threshold.",
    "signal over noise.",
    "explainable AI for technical careers.",
    "your career. your data. your machine.",
    "built for the ones who build things.",
    "anti-hallucination by design.",
    "never invents your experience.",
    "score it. understand it. own it.",
    "the job search, engineered.",
]

TIPS = [
    "nj diagnose → find out why interviews aren't coming",
    "nj gaps → see what to learn, ranked by ROI",
    "nj explain --job-id ID → see exactly why a job scored",
    "nj frame → tell your best story to the right audience",
    "nj calibrate --from-outcomes → let real data set your threshold",
    "nj prep --last → generate interview prep for your last application",
    "nj diff → see exactly what changed in your tailored CV",
    "nj watch → check Gmail for interview callbacks",
    "nj search --dry-run → scrape jobs without scoring (free)",
    "nj demo → see what nj produces without an API key",
    "nj ml train → train sponsorship + salary models on USCIS data",
    "nj intel company NAME → H1B history for any company",
    "nj graph build → build your career knowledge graph",
    "nj ml predict --company NAME --role TITLE → sponsorship probability",
    "nj postmortem → find out exactly why applications are failing",
    "nj enrich <url> → instant intelligence on any job URL",
]


def _is_tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def get_banner(version: str = "1.2.0") -> str:
    banner = random.choice(BANNERS)
    return banner.replace("{version}", version)


def show_banner(
    version: str = "1.2.0",
    db_path: str = "data/nj.db",
    show_stats: bool = True,
) -> None:
    banner = get_banner(version)
    tagline = random.choice(TAGLINES)
    tip = random.choice(TIPS)

    stats_line = ""
    if show_stats:
        stats_line = _get_quick_stats(db_path)

    banner_text = Text()
    banner_text.append(banner, style="bold cyan")
    banner_text.append(f"\n  {tagline}", style="dim white")
    if stats_line:
        banner_text.append(f"\n  {stats_line}", style="dim")
    banner_text.append(f"\n\n  [dim]tip:[/dim] {tip}")

    console.print(banner_text)
    console.print()


def _get_quick_stats(db_path: str) -> str:
    try:
        from pathlib import Path

        if not Path(db_path).exists():
            return ""
        from sqlalchemy import text

        from nj.db.engine import get_engine

        engine = get_engine(db_path)
        with engine.connect() as conn:
            try:
                jobs = conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar() or 0
                apps = (
                    conn.execute(
                        text("SELECT COUNT(*) FROM applications WHERE status='submitted'")
                    ).scalar()
                    or 0
                )
                # Tracked separately from `apps` so the banner never calls a
                # rendered-but-unsent draft an application.
                drafts = (
                    conn.execute(
                        text("SELECT COUNT(*) FROM applications WHERE status='generated'")
                    ).scalar()
                    or 0
                )
                scores = conn.execute(text("SELECT COUNT(*) FROM score_results")).scalar() or 0
                if jobs == 0 and apps == 0 and drafts == 0:
                    return ""
                parts = []
                if jobs > 0:
                    parts.append(f"{jobs} jobs tracked")
                if scores > 0:
                    parts.append(f"{scores} scored")
                if drafts > 0:
                    parts.append(f"{drafts} ready to send")
                if apps > 0:
                    parts.append(f"{apps} applied")
                return " · ".join(parts)
            except Exception:
                return ""
    except Exception:
        return ""
