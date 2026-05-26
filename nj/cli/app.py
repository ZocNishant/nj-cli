from __future__ import annotations

import typer

app = typer.Typer(
    name="nj",
    help="AI-powered job hunting CLI",
    no_args_is_help=True,
)


@app.callback()
def main(
    schedule: str = typer.Option(
        None,
        "--schedule",
        help="Set run schedule: N=days between runs, 0=disable, show=display",
    ),
) -> None:
    """nj — AI-powered job hunting CLI by Nishant Joshi."""
    if schedule is not None:
        from rich.console import Console

        from nj.scheduler.manager import set_schedule, show_schedule

        console = Console()
        if schedule == "show":
            show_schedule()
            raise typer.Exit()
        try:
            days = int(schedule)
            set_schedule(days)
            if days == 0:
                console.print("[yellow]Schedule disabled.[/yellow]")
            else:
                console.print(f"[green]Schedule set:[/green] every {days} day(s)")
            raise typer.Exit()
        except ValueError:
            console.print(
                f"[red]Invalid schedule value: {schedule}[/red]\n"
                "Use a number (days) or 'show'."
            )
            raise typer.Exit(1)


@app.command()
def init(
    config_path: str = typer.Option(
        "config.yaml", "--config", help="Path to config file"
    ),
) -> None:
    """Initialize nj — first-time setup wizard."""
    from nj.cli.cmd_init import run_init

    run_init(config_path=config_path)


@app.command()
def run(
    dry_run: bool = typer.Option(False, "--dry-run"),
    silent: bool = typer.Option(False, "--silent"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Run the full job hunting pipeline."""
    from nj.cli.cmd_run import run_pipeline
    from nj.models.config import Config

    config = Config.load()
    run_pipeline(config=config, db_path=db_path, dry_run=dry_run, silent=silent)


@app.command()
def search(
    dry_run: bool = typer.Option(False, "--dry-run"),
    db_path: str = typer.Option("data/nj.db", "--db"),
) -> None:
    """Search and score jobs without applying."""
    from nj.cli.cmd_search import run_search
    from nj.models.config import Config

    config = Config.load()
    run_search(config=config, db_path=db_path, dry_run=dry_run)


@app.command()
def tailor(
    url: str = typer.Argument(..., help="Job URL to tailor CV for"),
    db_path: str = typer.Option("data/nj.db", "--db"),
    output_dir: str = typer.Option("output", "--output"),
) -> None:
    """Tailor CV for a specific job URL."""
    from nj.cli.cmd_tailor import run_tailor
    from nj.models.config import Config

    config = Config.load()
    run_tailor(url=url, config=config, db_path=db_path, output_dir=output_dir)


@app.command()
def review(
    limit: int = typer.Option(
        50, "--limit", "-n", help="Max jobs to review per session"
    ),
    db_path: str = typer.Option("data/nj.db", "--db", help="Path to SQLite database"),
) -> None:
    """Review scored jobs interactively before applying."""
    from nj.cli.cmd_review import run_review
    from nj.models.config import Config

    config = Config.load()
    run_review(config=config, db_path=db_path, limit=limit)


@app.command()
def status(
    db_path: str = typer.Option("data/nj.db", "--db"),
    update_id: str = typer.Option(None, "--update-id", help="Application ID to update"),
    update_status_val: str = typer.Option(
        None, "--update-status", help="New status value"
    ),
) -> None:
    """Show application tracker dashboard."""
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
    """Label jobs to build calibration dataset."""
    from nj.cli.cmd_label import run_label
    from nj.models.config import Config

    config = Config.load()
    run_label(config=config, db_path=db_path, show_stats=stats)


@app.command()
def calibrate(
    db_path: str = typer.Option("data/nj.db", "--db"),
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    """Calibrate scoring threshold from scored jobs."""
    from nj.cli.cmd_calibrate import run_calibrate
    from nj.models.config import Config

    config = Config.load(config_path)
    run_calibrate(config=config, db_path=db_path, config_path=config_path)


@app.command()
def update_intern() -> None:
    """Generate CV bullets from your internship description."""
    from nj.cli.cmd_update_intern import run_update_intern
    from nj.models.config import Config

    config = Config.load()
    run_update_intern(config=config)


@app.command()
def logs(
    last_n: int = typer.Option(20, "--last", "-n"),
    log_file: str = typer.Option("logs/nj.log", "--file"),
) -> None:
    """View recent nj logs."""
    from nj.cli.cmd_logs import run_logs
    from nj.models.config import Config

    config = Config.load()
    run_logs(config=config, last_n=last_n, log_file=log_file)


@app.command()
def prep(
    job_id: str = typer.Option(None, "--job-id", "-j", help="Job ID from nj status"),
    url: str = typer.Option(None, "--url", "-u", help="Job URL to prep for"),
    last: bool = typer.Option(False, "--last", "-l", help="Prep for most recently applied job"),
    db_path: str = typer.Option("data/nj.db", "--db"),
    output_dir: str = typer.Option("output", "--output"),
) -> None:
    """Generate interview prep PDF for a job."""
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
def gaps(
    db_path: str = typer.Option("data/nj.db", "--db"),
    top_n: int = typer.Option(10, "--top", "-n", help="Number of gaps to show"),
    min_frequency: int = typer.Option(
        10, "--min-freq", help="Minimum % frequency to include a gap"
    ),
) -> None:
    """Analyse skill gaps across all scored jobs — ranked by ROI."""
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
    """Diagnose your CV — find out why you are or are not getting interviews."""
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
    """Scan Gmail for job callbacks and update application statuses."""
    from nj.cli.cmd_watch import run_watch
    from nj.models.config import Config

    config = Config.load()
    run_watch(config=config, db_path=db_path, days_back=days_back, setup=setup, dry_run=dry_run)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Print config to terminal"),
    config_path: str = typer.Option("config.yaml", "--path"),
) -> None:
    """View or edit nj configuration."""
    from nj.cli.cmd_config import run_config
    from nj.models.config import Config

    cfg = Config.load(config_path)
    run_config(config=cfg, config_path=config_path, show=show)
