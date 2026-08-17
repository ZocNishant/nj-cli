from __future__ import annotations

import sys

import typer

__version__ = "1.2.0"

app = typer.Typer(
    name="nj",
    help="AI career operating system",
    no_args_is_help=True,
)


def main_entry() -> None:
    """Entry point: bare 'nj' launches the interactive shell; anything
    with arguments delegates to the Typer app as usual."""
    from nj.utils.secrets import bootstrap

    bootstrap()
    if len(sys.argv) == 1:
        from nj.cli.shell import run_shell

        run_shell(version=__version__)
    else:
        app()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        is_eager=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed debug output"),
    schedule: str = typer.Option(
        None,
        "--schedule",
        help="Set schedule: N=days, 0=disable, show=display",
    ),
) -> None:
    """nj — AI career operating system."""
    if version:
        from rich.console import Console as RC

        RC().print(f"nj-cli [bold]v{__version__}[/bold]")
        raise typer.Exit()

    if verbose:
        from nj.utils.logger import set_verbose, setup_logger

        set_verbose(True)
        setup_logger(level="DEBUG", console_level="DEBUG")

    if schedule is not None:
        from rich.console import Console as RC2

        from nj.scheduler.manager import set_schedule, show_schedule

        rc = RC2()
        if schedule == "show":
            show_schedule()
            raise typer.Exit()
        try:
            days = int(schedule)
            set_schedule(days)
            if days == 0:
                rc.print("[yellow]Schedule disabled.[/yellow]")
            else:
                rc.print(f"[green]Schedule set:[/green] every {days} day(s)")
            raise typer.Exit()
        except ValueError:
            rc.print(f"[red]Invalid:[/red] {schedule}")
            raise typer.Exit(1)

    if ctx.invoked_subcommand is None:
        from nj.cli.shell import run_shell

        run_shell(version=__version__)
        raise typer.Exit()


@app.command()
def demo() -> None:
    """Interactive demo — see nj output without API key."""
    from nj.cli.cmd_demo import run_demo

    run_demo()


@app.command()
def init(
    config_path: str = typer.Option("config.yaml", "--config", help="Path to config file"),
) -> None:
    """First-time setup wizard — API keys, CV, email, schedule."""
    from nj.cli.cmd_init import run_init

    run_init(config_path=config_path)


@app.command()
def run(
    dry_run: bool = typer.Option(False, "--dry-run"),
    silent: bool = typer.Option(False, "--silent"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Full pipeline: scrape jobs, score, tailor CV, apply."""
    from nj.cli.cmd_run import run_pipeline
    from nj.models.config import Config

    config = Config.load()
    run_pipeline(config=config, db_path=db_path, dry_run=dry_run, silent=silent)


@app.command()
def search(
    dry_run: bool = typer.Option(False, "--dry-run"),
    db_path: str = typer.Option("data/nj.db", "--db"),
    level: str = typer.Option(
        None,
        "--level",
        "-l",
        help="Seniority filter: junior, mid, senior, staff",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Max jobs to score (default: 50, use 0 for all)",
    ),
    all_langs: bool = typer.Option(
        False,
        "--all-langs",
        help="Include non-English job listings",
    ),
    visa: str = typer.Option(
        "any",
        "--visa",
        help="sponsor=confirmed/likely only, any=all (default: any)",
    ),
) -> None:
    """Scrape and score jobs without applying — review first."""
    from nj.cli.cmd_search import run_search
    from nj.models.config import Config

    config = Config.load()
    run_search(
        config=config,
        db_path=db_path,
        dry_run=dry_run,
        level=level,
        limit=limit,
        all_langs=all_langs,
        visa_mode=visa,
    )


@app.command()
def tailor(
    url: str = typer.Argument(..., help="Job URL to tailor CV for"),
    db_path: str = typer.Option("data/nj.db", "--db"),
    output_dir: str = typer.Option("output", "--output"),
) -> None:
    """Tailor your CV and generate cover letter for a job URL."""
    from nj.cli.cmd_tailor import run_tailor
    from nj.models.config import Config

    config = Config.load()
    run_tailor(url=url, config=config, db_path=db_path, output_dir=output_dir)


@app.command()
def review(
    limit: int = typer.Option(50, "--limit", "-n", help="Max jobs to review per session"),
    db_path: str = typer.Option("data/nj.db", "--db", help="Path to SQLite database"),
) -> None:
    """Interactively review scored jobs before applying."""
    from nj.cli.cmd_review import run_review
    from nj.models.config import Config

    config = Config.load()
    run_review(config=config, db_path=db_path, limit=limit)


@app.command()
def status(
    db_path: str = typer.Option("data/nj.db", "--db"),
    update_id: str = typer.Option(None, "--update-id", help="Application ID to update"),
    update_status_val: str = typer.Option(None, "--update-status", help="New status value"),
) -> None:
    """Application tracker — history, scores, trajectory."""
    from nj.cli.cmd_status import run_status
    from nj.models.config import Config

    config = Config.load()
    run_status(
        config=config,
        db_path=db_path,
        update_id=update_id,
        update_status=update_status_val,
    )


@app.command()
def label(
    db_path: str = typer.Option("data/nj.db", "--db"),
    stats: bool = typer.Option(False, "--stats", help="Show label distribution stats"),
) -> None:
    """Label jobs yes/no/maybe to build calibration dataset."""
    from nj.cli.cmd_label import run_label
    from nj.models.config import Config

    config = Config.load()
    run_label(config=config, db_path=db_path, show_stats=stats)


@app.command()
def calibrate(
    db_path: str = typer.Option("data/nj.db", "--db"),
    config_path: str = typer.Option("config.yaml", "--config"),
    from_outcomes: bool = typer.Option(
        False, "--from-outcomes", help="Calibrate using real interview outcome data"
    ),
) -> None:
    """Tune score threshold from data or real interview outcomes."""
    from nj.models.config import Config

    config = Config.load(config_path)
    if from_outcomes:
        from nj.cli.cmd_calibrate import run_calibrate_from_outcomes

        run_calibrate_from_outcomes(config=config, db_path=db_path, config_path=config_path)
    else:
        from nj.cli.cmd_calibrate import run_calibrate

        run_calibrate(config=config, db_path=db_path, config_path=config_path)


@app.command()
def update_role() -> None:
    """Generate CV bullets for any experience entry from plain English."""
    from nj.cli.cmd_update_role import run_update_role
    from nj.models.config import Config

    config = Config.load()
    run_update_role(config=config)


@app.command()
def update_intern() -> None:
    """Alias for update-role (backward-compatible)."""
    from nj.cli.cmd_update_intern import run_update_intern
    from nj.models.config import Config

    config = Config.load()
    run_update_intern(config=config)


@app.command()
def update_cv(
    section: str = typer.Option(
        None,
        "--section",
        "-s",
        help=("Section to update: summary, skills, research_interests, soft_skills, personal"),
    ),
    show: bool = typer.Option(
        False, "--show", help="Show all editable sections and current values"
    ),
) -> None:
    """Update CV sections interactively — no JSON editing needed."""
    from nj.cli.cmd_update_cv import run_update_cv
    from nj.models.config import Config

    config = Config.load()
    run_update_cv(config=config, section=section, show=show)


@app.command()
def logs(
    last_n: int = typer.Option(20, "--last", "-n"),
    log_file: str = typer.Option("logs/nj.log", "--file"),
    stats: bool = typer.Option(False, "--stats", help="Show reliability statistics"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """View recent logs or reliability stats."""
    from nj.cli.cmd_logs import run_logs
    from nj.models.config import Config

    config = Config.load()
    run_logs(
        config=config,
        last_n=last_n,
        log_file=log_file,
        show_stats=stats,
        db_path=db_path,
    )


@app.command()
def prep(
    job_id: str = typer.Option(None, "--job-id", "-j", help="Job ID from nj status"),
    url: str = typer.Option(None, "--url", "-u", help="Job URL to prep for"),
    last: bool = typer.Option(False, "--last", "-l", help="Prep for most recently applied job"),
    db_path: str = typer.Option("data/nj.db", "--db"),
    output_dir: str = typer.Option("output", "--output"),
) -> None:
    """Generate interview prep PDF for a specific job."""
    from nj.cli.cmd_prep import run_prep
    from nj.models.config import Config

    config = Config.load()
    run_prep(
        config=config,
        job_id=job_id,
        url=url,
        last=last,
        db_path=db_path,
        output_dir=output_dir,
    )


@app.command()
def quality(
    job_id: str = typer.Option(None, "--job-id", "-j", help="Check a specific job by ID"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Run pre-submit quality gate on tailored applications."""
    from nj.cli.cmd_quality import run_quality_check
    from nj.models.config import Config

    config = Config.load()
    run_quality_check(config=config, job_id=job_id, db_path=db_path)


@app.command()
def frame(
    project_id: str = typer.Option(
        None, "--project", "-p", help="Project ID to frame (see nj frame --list)"
    ),
    audience: str = typer.Option(
        None,
        "--audience",
        "-a",
        help="Target audience: production_ml, research_lab, healthtech_startup, big_tech, early_stage_startup, custom",
    ),
    role_description: str = typer.Option("", "--role", help="Role description for custom audience"),
    list_projects: bool = typer.Option(False, "--list", "-l", help="List available projects"),
) -> None:
    """Reframe a project for a specific audience or role type."""
    from nj.cli.cmd_frame import run_frame
    from nj.models.config import Config

    config = Config.load()
    run_frame(
        config=config,
        project_id=project_id,
        audience=audience,
        role_description=role_description,
        list_projects=list_projects,
    )


@app.command()
def gaps(
    db_path: str = typer.Option("data/nj.db", "--db"),
    top_n: int = typer.Option(10, "--top", "-n", help="Number of gaps to show"),
    min_frequency: int = typer.Option(
        10, "--min-freq", help="Minimum % frequency to include a gap"
    ),
) -> None:
    """Analyse skill gaps across scored jobs — ranked by ROI."""
    from nj.cli.cmd_gaps import run_gaps
    from nj.models.config import Config

    config = Config.load()
    run_gaps(config=config, db_path=db_path, top_n=top_n, min_frequency=min_frequency)


@app.command()
def diagnose(
    db_path: str = typer.Option("data/nj.db", "--db"),
    output_dir: str = typer.Option("output", "--output"),
    no_pdf: bool = typer.Option(
        False, "--no-pdf", help="Skip PDF generation, terminal output only"
    ),
) -> None:
    """Diagnose your CV — find out why interviews are not coming."""
    from nj.cli.cmd_diagnose import run_diagnose
    from nj.models.config import Config

    config = Config.load()
    run_diagnose(config=config, db_path=db_path, output_dir=output_dir, no_pdf=no_pdf)


@app.command()
def watch(
    days_back: int = typer.Option(7, "--days", "-d", help="Days back to scan Gmail"),
    db_path: str = typer.Option("data/nj.db", "--db"),
    setup: bool = typer.Option(False, "--setup", help="Show Gmail OAuth2 setup instructions"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Detect callbacks without updating DB"),
) -> None:
    """Check Gmail for interview callbacks and offer signals."""
    from nj.cli.cmd_watch import run_watch
    from nj.models.config import Config

    config = Config.load()
    run_watch(
        config=config,
        db_path=db_path,
        days_back=days_back,
        setup=setup,
        dry_run=dry_run,
    )


@app.command()
def diff(
    job_id: str = typer.Option(
        None,
        "--job-id",
        "-j",
        help="Job ID to diff (first 8 chars work)",
    ),
    section: str = typer.Option(
        None,
        "--section",
        "-s",
        help="Section to diff: summary, skills, experience, projects",
    ),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Show exactly what changed between base CV and tailored CV."""
    from nj.cli.cmd_diff import run_diff
    from nj.models.config import Config

    config = Config.load()
    run_diff(
        config=config,
        job_id=job_id,
        section=section,
        db_path=db_path,
    )


@app.command()
def explain(
    job_id: str = typer.Option(
        None,
        "--job-id",
        "-j",
        help="Job ID to explain (first 8 chars work too)",
    ),
    top_n: int = typer.Option(
        10,
        "--top",
        "-n",
        help="Show top N scored jobs when no ID given",
    ),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Explain exactly why a job scored the way it did."""
    from nj.cli.cmd_explain import run_explain
    from nj.models.config import Config

    config = Config.load()
    run_explain(
        config=config,
        job_id=job_id,
        top_n=top_n,
        db_path=db_path,
    )


@app.command()
def ml(
    subcommand: str = typer.Argument(
        "status",
        help="status | train | predict | salary | semantic",
    ),
    company: str = typer.Option("", "--company", "-c"),
    role: str = typer.Option("", "--role", "-r"),
    state: str = typer.Option("CA", "--state", "-s"),
    year: int = typer.Option(2024, "--year", "-y"),
    job_id: str = typer.Option(None, "--job-id", "-j"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """ML models — sponsorship probability, salary prediction, semantic matching."""
    from nj.cli.cmd_ml import run_ml
    from nj.models.config import Config

    config = Config.load()
    run_ml(
        config=config,
        subcommand=subcommand,
        company=company,
        role=role,
        state=state,
        year=year,
        job_id=job_id,
        db_path=db_path,
    )


@app.command()
def graph(
    subcommand: str = typer.Argument(
        "stats",
        help="build | show | stats | skills | companies | path",
    ),
    query: str = typer.Argument("", help="From node (for path command)"),
    target: str = typer.Option("", "--target", "-t", help="Target node (for path command)"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Career knowledge graph — your career as connected data."""
    from nj.cli.cmd_graph import run_graph
    from nj.models.config import Config

    config = Config.load()
    run_graph(
        config=config,
        subcommand=subcommand,
        query=query,
        target=target,
        db_path=db_path,
    )


@app.command()
def intel(
    subcommand: str = typer.Argument(None, help="sync | company | top | role | search | stats"),
    query: str = typer.Argument("", help="Company name, role query, or search term"),
    state: str = typer.Option("", "--state", "-s", help="Filter by state (e.g. CA, NY)"),
    year: int = typer.Option(0, "--year", "-y", help="Filter by year (2022–2024)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results to show"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """H1B sponsorship intelligence — who sponsors ML/AI visas and for how much."""
    from nj.cli.cmd_intel import run_intel

    run_intel(
        subcommand=subcommand,
        query=query,
        state=state,
        year=year,
        limit=limit,
        db_path=db_path,
    )


@app.command()
def enrich(
    url: str = typer.Argument(None, help="Job URL to analyze"),
    no_score: bool = typer.Option(
        False, "--no-score", help="Skip AI scoring (faster, no API credits)"
    ),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Instant intelligence report for any job URL."""
    from nj.cli.cmd_enrich import run_enrich
    from nj.models.config import Config

    config = Config.load()
    run_enrich(config=config, url=url, no_score=no_score, db_path=db_path)


@app.command()
def postmortem(
    db_path: str = typer.Option("data/nj.db", "--db"),
    min_applications: int = typer.Option(
        3,
        "--min",
        help="Minimum applications needed for analysis",
    ),
) -> None:
    """Analyse application failure patterns — why are you not getting interviews."""
    from nj.cli.cmd_postmortem import run_postmortem
    from nj.models.config import Config

    config = Config.load()
    run_postmortem(
        config=config,
        db_path=db_path,
        min_applications=min_applications,
    )


@app.command()
def manual(
    command: str = typer.Argument(None, help="Command to get help for"),
) -> None:
    """Full command reference — every flag and example."""
    from nj.cli.cmd_help_full import run_manual
    from nj.models.config import Config

    config = Config.load()
    run_manual(config=config, command=command)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Print config to terminal"),
    config_path: str = typer.Option("config.yaml", "--path"),
    check_provider: bool = typer.Option(
        False, "--check-provider", help="Test the configured LLM provider"
    ),
) -> None:
    """View, edit, or test the configured LLM provider."""
    from nj.cli.cmd_config import run_config
    from nj.models.config import Config

    cfg = Config.load(config_path)
    run_config(
        config=cfg,
        config_path=config_path,
        show=show,
        check_provider=check_provider,
    )
