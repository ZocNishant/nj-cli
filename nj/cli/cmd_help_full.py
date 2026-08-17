"""
Full command reference — every command, flag, and example.
Accessible via: nj manual
"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

COMMAND_REFERENCE = {
    "search": {
        "description": "Scrape jobs from all enabled sources, enrich with intelligence, and score against your CV.",
        "flags": [
            ("--dry-run", "Scrape only — no scoring, no API credits used"),
            ("--verbose / -v", "Show per-scraper debug output"),
            ("--db PATH", "Database path (default: data/nj.db)"),
        ],
        "examples": [
            ("nj search", "Full scrape + enrich + score"),
            ("nj search --dry-run", "Scrape only, see what's out there"),
        ],
        "notes": "Runs all 7 scrapers in parallel. Ghost jobs filtered automatically. Results saved to DB.",
    },
    "enrich": {
        "description": "Full intelligence report for any job URL — sponsorship probability, salary estimate, USCIS data, semantic match.",
        "flags": [
            (
                "URL",
                "Job URL (required) — works with LinkedIn, Greenhouse, Lever, Workday, any job board",
            ),
            ("--no-score", "Skip AI scoring (faster, no API credits)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj enrich https://jobs.lever.co/company/job-id", "Full intelligence on a Lever job"),
            (
                "nj enrich https://linkedin.com/jobs/view/123 --no-score",
                "Quick intel without scoring",
            ),
        ],
        "notes": "Works without API key for sponsorship/salary/USCIS layers. Needs API key for AI scoring.",
    },
    "explain": {
        "description": "Explain exactly why a job scored the way it did — 6 sub-scores, evidence, enrichment data.",
        "flags": [
            ("--job-id / -j ID", "Job ID to explain (first 8 chars work)"),
            ("--top / -n N", "Show top N jobs when no ID given (default: 10)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj explain", "Show top 10 scored jobs"),
            ("nj explain --job-id abc123", "Full explanation for specific job"),
        ],
        "notes": "Shows sponsorship probability, USCIS history, salary estimate, and semantic match alongside AI scores.",
    },
    "diagnose": {
        "description": "Full CV health report — root causes of interview failure, recruiter first impression, ATS concerns.",
        "flags": [
            ("--no-pdf", "Terminal output only, skip PDF generation"),
            ("--db PATH", "Database path"),
            ("--output DIR", "Output directory for PDF (default: output/)"),
        ],
        "examples": [
            ("nj diagnose", "Full diagnosis with PDF report"),
            ("nj diagnose --no-pdf", "Quick terminal-only diagnosis"),
        ],
        "notes": "Uses career graph context if built. Requires API key. PDF saved to output/.",
    },
    "gaps": {
        "description": "Skill gap analysis across all scored jobs — ranked by frequency and estimated score impact.",
        "flags": [
            ("--top / -n N", "Number of gaps to show (default: 10)"),
            ("--min-freq N", "Minimum frequency % to include (default: 10)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj gaps", "Top 10 skill gaps"),
            ("nj gaps --top 20", "Top 20 gaps"),
        ],
        "notes": "No API calls. Pure aggregation of existing score data. Run nj search first.",
    },
    "frame": {
        "description": "Reframe your best project for a specific audience — production ML, research lab, healthtech, big tech.",
        "flags": [
            ("--project / -p ID", "Project ID to frame (see nj frame --list)"),
            (
                "--audience / -a TYPE",
                "Target: production_ml, research_lab, healthtech_startup, big_tech, early_stage_startup, custom",
            ),
            ("--role TEXT", "Role description for custom audience"),
            ("--list / -l", "List available projects"),
        ],
        "examples": [
            ("nj frame --list", "See all projects in CV"),
            (
                "nj frame --project gastrovision --audience healthtech_startup",
                "Frame GastroVision for healthtech",
            ),
            ("nj frame --audience research_lab", "Frame anchor project for research"),
        ],
        "notes": "Anti-hallucination validated. Only reframes existing content — never invents.",
    },
    "diff": {
        "description": "Show exactly what changed between your base CV and the tailored version for a job.",
        "flags": [
            ("--job-id / -j ID", "Job ID to diff"),
            ("--section / -s NAME", "Section to diff: summary, skills, experience, projects"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj diff", "List jobs with tailored CVs"),
            ("nj diff --job-id abc123", "Full diff for specific job"),
            ("nj diff --job-id abc123 --section skills", "Skills diff only"),
        ],
        "notes": "Requires nj tailor or nj run to have generated a tailored CV first.",
    },
    "postmortem": {
        "description": "Analyse application failure patterns — why interviews are not coming, what to fix.",
        "flags": [
            ("--min N", "Minimum applications for analysis (default: 3)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj postmortem", "Full failure analysis"),
        ],
        "notes": "No API calls. Detects patterns: low scores, high no-response rate, visa issues, weak experience sub-scores.",
    },
    "intel": {
        "description": "H1B sponsorship intelligence powered by public USCIS petition data.",
        "flags": [
            ("sync", "Download latest USCIS H1B data (~2-3 min first run)"),
            ("top", "Top ML/AI sponsors"),
            ("company NAME", "H1B profile for a specific company"),
            ("role TITLE", "Which companies sponsor this role"),
            ("stats", "Database statistics"),
            ("--state / -s ST", "Filter by US state (CA, NY, TX, FL...)"),
            ("--year / -y YEAR", "Filter by year (2022, 2023, 2024)"),
            ("--limit / -n N", "Number of results (default: 20)"),
        ],
        "examples": [
            ("nj intel sync", "Download USCIS data (run once)"),
            ("nj intel top", "Top ML sponsors nationwide"),
            ("nj intel top --state FL", "Top ML sponsors in Florida"),
            ("nj intel company Google", "Google H1B history"),
            ("nj intel company 'Moffitt Cancer Center'", "Moffitt H1B profile"),
            ("nj intel role 'Machine Learning Engineer'", "Who sponsors ML Engineers"),
            ("nj intel stats", "How much data is loaded"),
        ],
        "notes": "Data source: USCIS H1B Employer Data Hub (public). Updated quarterly. Free.",
    },
    "graph": {
        "description": "Career knowledge graph — your skills, companies, projects, and applications as connected data.",
        "flags": [
            ("build", "Build graph from CV + existing scores"),
            ("show", "Visualize your career tree"),
            ("stats", "Graph statistics"),
            ("skills", "Your skills vs gap skills"),
            ("companies", "Companies in your graph"),
            ("path FROM TO", "Shortest path between two nodes"),
            ("--target / -t NODE", "Target node for path command"),
        ],
        "examples": [
            ("nj graph build", "Build from cv_base.json + DB"),
            ("nj graph show", "See your career as a tree"),
            ("nj graph path PyTorch 'Senior ML Engineer'", "Skill path to target role"),
            ("nj graph skills", "Skills you have vs skills you need"),
        ],
        "notes": "Auto-updates on every application. No API calls needed.",
    },
    "ml": {
        "description": "ML models — sponsorship probability classifier, salary predictor, semantic CV-JD similarity.",
        "flags": [
            ("status", "Show which models are trained"),
            ("train", "Train models on USCIS data (requires nj intel sync first)"),
            ("predict", "Sponsorship probability for company + role"),
            ("salary", "Salary prediction for role + location"),
            ("semantic", "Semantic CV-JD similarity for a scored job"),
            ("--company / -c NAME", "Company name for predict"),
            ("--role / -r TITLE", "Role title for predict/salary"),
            ("--state / -s ST", "State for salary (default: CA)"),
            ("--year / -y YEAR", "Year for salary (default: 2024)"),
            ("--job-id / -j ID", "Job ID for semantic"),
        ],
        "examples": [
            ("nj ml status", "See model status"),
            ("nj ml train", "Train on USCIS data"),
            ("nj ml predict --company Google --role 'ML Engineer'", "Sponsorship probability"),
            ("nj ml salary --role 'Computer Vision Engineer' --state CA", "Salary estimate"),
            ("nj ml semantic --job-id abc123", "Semantic match for scored job"),
        ],
        "notes": "Sponsorship + salary need nj intel sync + nj ml train. Semantic needs: pip install sentence-transformers.",
    },
    "prep": {
        "description": "Generate interview prep PDF — technical questions, STAR behavioural, story bank, quick reference.",
        "flags": [
            ("--job-id / -j ID", "Job ID from nj status"),
            ("--url / -u URL", "Job URL to prep for"),
            ("--last / -l", "Prep for most recently applied job"),
            ("--output DIR", "Output directory (default: output/)"),
        ],
        "examples": [
            ("nj prep --last", "Prep for your last application"),
            ("nj prep --job-id abc123", "Prep for specific job"),
            ("nj prep --url https://...", "Prep for any job URL"),
        ],
        "notes": "Generates PDF with 8-10 technical questions with confidence ratings. Requires API key.",
    },
    "review": {
        "description": "Interactively review scored jobs before applying.",
        "flags": [
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj review", "Start review queue"),
        ],
        "notes": "Keys: a=approve, s=skip, l=label, v=view in browser, q=quit. Only approved jobs proceed to apply.",
    },
    "status": {
        "description": "Application tracker — history, scores, trajectory view, ML intelligence summary.",
        "flags": [
            ("--update-id ID", "Job ID to update status for"),
            ("--update-status STATUS", "New status value"),
            ("--no-trajectory", "Hide weekly trajectory view"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj status", "Full dashboard"),
            ("nj status --no-trajectory", "Just the table"),
            ("nj status --update-id abc123 --update-status interview", "Mark as interview"),
        ],
        "notes": "Shows weekly application trajectory and conversion rates when outcome data is available.",
    },
    "calibrate": {
        "description": "Tune score threshold from distribution data or real interview outcome data.",
        "flags": [
            ("--from-outcomes", "Calibrate from real interview callbacks (recommended)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj calibrate", "Interactive threshold tuning"),
            ("nj calibrate --from-outcomes", "Data-driven threshold from interview data"),
        ],
        "notes": "Run after nj watch detects interview callbacks. Threshold updates config.yaml.",
    },
    "watch": {
        "description": "Check Gmail for interview callbacks and offer signals. Auto-updates application outcomes.",
        "flags": [
            ("--setup", "Configure Gmail OAuth credentials"),
            ("--days N", "Days back to check (default: 30)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj watch --setup", "First-time Gmail setup"),
            ("nj watch", "Check for callbacks"),
            ("nj watch --days 7", "Check last 7 days only"),
        ],
        "notes": "Detects interview/rejection/offer signals. Updates DB outcomes. Triggers nj prep suggestion.",
    },
    "tailor": {
        "description": "Tailor CV and generate cover letter for a specific job URL.",
        "flags": [
            ("URL", "Job URL (required)"),
            ("--output DIR", "Output directory (default: output/)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj tailor https://jobs.lever.co/company/job", "Tailor for a Lever job"),
        ],
        "notes": "Anti-hallucination validated. LaTeX → PDF via tectonic. Saves JSON for nj diff.",
    },
    "update-cv": {
        "description": "Update CV sections interactively — no JSON editing needed.",
        "flags": [
            (
                "--section / -s NAME",
                "Section: summary, skills, research_interests, soft_skills, personal",
            ),
            ("--show", "Display all sections and current values"),
        ],
        "examples": [
            ("nj update-cv --show", "See all editable sections"),
            ("nj update-cv --section summary", "Update summary"),
            ("nj update-cv --section personal", "Update contact info"),
        ],
        "notes": "Saves to cv/cv_base.json. Complex sections (skills dict) suggest editing JSON directly.",
    },
    "update-role": {
        "description": "Generate CV bullets for any experience entry from plain English.",
        "flags": [],
        "examples": [
            ("nj update-role", "Interactive bullet generator for any role"),
        ],
        "notes": "Select an experience entry, describe your work in plain English → Claude generates 3-4 ATS-friendly bullets → preview + confirm → saves to cv_base.json.",
    },
    "init": {
        "description": "First-time setup wizard — API keys, CV import, email, schedule.",
        "flags": [],
        "examples": [
            ("nj init", "Run setup wizard"),
        ],
        "notes": "7-step wizard. Tests API key live. Can import CV from PDF. Creates config.yaml and .env.",
    },
    "run": {
        "description": "Full pipeline — scrape, enrich, score, tailor, quality gate, apply, notify.",
        "flags": [
            ("--dry-run", "Scrape + score only, no applying"),
            ("--silent", "Suppress terminal output (for cron)"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj run --dry-run", "Full pipeline without applying"),
            ("nj run --silent", "Scheduled silent run"),
        ],
        "notes": "Phase 1 (default): requires human review before applying. Set automation_phase in config to change.",
    },
    "demo": {
        "description": "Interactive demo using sample data — see what nj produces without an API key.",
        "flags": [],
        "examples": [
            ("nj demo", "Run the demo"),
        ],
        "notes": "No API key needed. Shows scored job, CV diagnosis, skill gaps using bundled sample data.",
    },
    "logs": {
        "description": "View recent logs or reliability statistics.",
        "flags": [
            ("--last / -n N", "Show last N log lines (default: 20)"),
            ("--stats", "Show parse failure rate and reliability metrics"),
            ("--file PATH", "Log file path (default: logs/nj.log)"),
        ],
        "examples": [
            ("nj logs", "Last 20 log entries"),
            ("nj logs --last 50", "Last 50 entries"),
            ("nj logs --stats", "Reliability statistics"),
        ],
        "notes": "Parse failure rate >5% triggers a warning — means scoring prompt needs attention.",
    },
    "config": {
        "description": "View, edit, or test configuration.",
        "flags": [
            ("--show", "Display config.yaml with syntax highlighting"),
            ("--check-provider", "Send test ping to configured LLM provider"),
            ("--path PATH", "Config file path (default: config.yaml)"),
        ],
        "examples": [
            ("nj config --show", "View current config"),
            ("nj config --check-provider", "Test Claude/FreeLLMAPI connection"),
        ],
        "notes": "Opens $EDITOR by default. Use --show for read-only view.",
    },
    "quality": {
        "description": "Run pre-submit quality gate on tailored applications.",
        "flags": [
            ("--job-id / -j ID", "Check specific job"),
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj quality", "Check all tailored jobs"),
            ("nj quality --job-id abc123", "Check specific job"),
        ],
        "notes": "Blocks: score below threshold, no-sponsorship language. Warns: banned phrases, senior signals, low confidence.",
    },
    "label": {
        "description": "Label jobs yes/no/maybe to build calibration dataset.",
        "flags": [
            ("--db PATH", "Database path"),
        ],
        "examples": [
            ("nj label", "Start labeling queue"),
        ],
        "notes": "Builds dataset for nj calibrate. More labels = better threshold calibration.",
    },
    "manual": {
        "description": "Full command reference with every flag, example, and note.",
        "flags": [
            ("COMMAND", "Command to get detailed help for (optional)"),
        ],
        "examples": [
            ("nj manual", "Show full command reference"),
            ("nj manual intel", "Detailed help for intel command"),
            ("nj manual ml", "Detailed help for ml command"),
        ],
        "notes": "Also accessible as nj manual <command> for focused help on any single command.",
    },
}


def run_manual(
    config=None,
    command: str | None = None,
) -> None:
    if command and command in COMMAND_REFERENCE:
        _show_command_detail(command)
        return

    if command:
        console.print(
            f"[red]Unknown command:[/red] {command}\n"
            "Run [bold]nj manual[/bold] to see all commands."
        )
        return

    _show_full_manual()


def _show_command_detail(command: str) -> None:
    ref = COMMAND_REFERENCE[command]

    console.print(
        Panel(
            f"[bold]nj {command}[/bold]\n\n{ref['description']}",
            title=f"nj {command}",
            border_style="cyan",
        )
    )

    if ref.get("flags"):
        table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
        table.add_column("Flag", style="cyan", width=30)
        table.add_column("Description", width=50)
        for flag, desc in ref["flags"]:
            table.add_row(flag, desc)
        console.print(Rule("[dim]Flags[/dim]"))
        console.print(table)

    if ref.get("examples"):
        console.print(Rule("[dim]Examples[/dim]"))
        for cmd, desc in ref["examples"]:
            console.print(f"  [bold cyan]{cmd}[/bold cyan]\n  [dim]{desc}[/dim]\n")

    if ref.get("notes"):
        console.print(f"[dim]Note: {ref['notes']}[/dim]")


def _show_full_manual() -> None:
    console.print(
        Panel(
            "[bold]nj-cli — AI Career Operating System[/bold]\n\n"
            "Anti-hallucination CV tailoring · "
            "Explainable scoring · H1B intelligence\n"
            "Career knowledge graph · ML models · "
            "Interactive shell\n\n"
            "[dim]Usage: nj <command> [flags]\n"
            "Shell: nj → then type commands interactively\n"
            "Help:  nj manual <command> for detailed help[/dim]",
            border_style="cyan",
        )
    )

    sections = {
        "Intelligence": ["diagnose", "gaps", "explain", "diff", "frame", "postmortem"],
        "Job discovery": ["search", "enrich", "tailor", "review", "quality"],
        "Data & ML": ["intel", "graph", "ml"],
        "Applications": ["run", "status", "calibrate", "label", "watch", "prep"],
        "CV management": ["update-cv", "update-role"],
        "System": ["init", "demo", "logs", "config", "manual"],
    }

    for section, commands in sections.items():
        console.print(f"\n[bold white]{section}[/bold white]")
        for cmd in commands:
            ref = COMMAND_REFERENCE.get(cmd, {})
            desc = ref.get("description", "")[:60]
            console.print(f"  [cyan]{cmd:<18}[/cyan] [dim]{desc}[/dim]")

    console.print(
        "\n[dim]Run [bold]nj manual <command>[/bold] for detailed help on any command.[/dim]\n"
    )
