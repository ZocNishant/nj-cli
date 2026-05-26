from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nj.integrations.gmail_watcher import CallbackSignal
from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_watch(
    config: Config,
    db_path: str = "data/nj.db",
    days_back: int = 7,
    setup: bool = False,
    dry_run: bool = False,
) -> None:
    from nj.integrations.gmail_watcher import check_callbacks, update_application_statuses

    if setup:
        _run_setup()
        return

    console.print(
        Panel(
            f"[dim]Scanning Gmail for job callbacks (last {days_back} days)...[/dim]",
            title="nj watch",
            border_style="cyan",
        )
    )

    credentials_path = "gmail_credentials.json"
    token_path = ".gmail_token.json"

    callbacks = check_callbacks(
        db_path=db_path,
        days_back=days_back,
        credentials_path=credentials_path,
        token_path=token_path,
    )

    if not callbacks:
        console.print("[yellow]No job callbacks detected in the last "
                      f"{days_back} days.[/yellow]")
        return

    _display_callbacks(callbacks)

    if not dry_run:
        updated = update_application_statuses(callbacks, db_path=db_path)
        if updated:
            console.print(
                f"\n[green]Updated {updated} application status(es).[/green]"
            )

    if config.notify.email_to:
        _send_notifications(callbacks, config)


def _display_callbacks(callbacks: list[dict]) -> None:
    signal_colors = {
        CallbackSignal.INTERVIEW: "cyan",
        CallbackSignal.OFFER: "green",
        CallbackSignal.REJECTION: "red",
        CallbackSignal.UNKNOWN: "dim",
    }
    signal_labels = {
        CallbackSignal.INTERVIEW: "INTERVIEW",
        CallbackSignal.OFFER: "OFFER",
        CallbackSignal.REJECTION: "REJECTION",
        CallbackSignal.UNKNOWN: "UNKNOWN",
    }

    table = Table(title=f"Callbacks detected ({len(callbacks)})", border_style="cyan")
    table.add_column("Signal", style="bold", width=12)
    table.add_column("Company", width=20)
    table.add_column("Subject", width=50)

    for cb in callbacks:
        signal = cb.get("signal", CallbackSignal.UNKNOWN)
        color = signal_colors.get(signal, "dim")
        label = signal_labels.get(signal, signal.upper())
        app = cb.get("application")
        company = app.company if app else "Unknown"
        subject = (cb.get("subject") or "")[:48]
        table.add_row(
            f"[{color}]{label}[/{color}]",
            company,
            subject,
        )

    console.print(table)


def _send_notifications(callbacks: list[dict], config: Config) -> None:
    from nj.notify.email import EmailNotifier

    interviews = [c for c in callbacks if c["signal"] == CallbackSignal.INTERVIEW]
    offers = [c for c in callbacks if c["signal"] == CallbackSignal.OFFER]
    rejections = [c for c in callbacks if c["signal"] == CallbackSignal.REJECTION]

    lines = []
    if offers:
        lines.append(f"OFFERS ({len(offers)}):")
        for c in offers:
            app = c.get("application")
            lines.append(f"  - {app.company if app else 'Unknown'}: {c.get('subject', '')}")
    if interviews:
        lines.append(f"\nINTERVIEWS ({len(interviews)}):")
        for c in interviews:
            app = c.get("application")
            lines.append(f"  - {app.company if app else 'Unknown'}: {c.get('subject', '')}")
    if rejections:
        lines.append(f"\nREJECTIONS ({len(rejections)}):")
        for c in rejections:
            app = c.get("application")
            lines.append(f"  - {app.company if app else 'Unknown'}: {c.get('subject', '')}")

    body = "\n".join(lines)
    notifier = EmailNotifier(config.notify)
    try:
        notifier._send(
            subject=f"nj watch: {len(callbacks)} callback(s) detected",
            body=body,
        )
        console.print(f"[green]Summary emailed to {config.notify.email_to}[/green]")
    except Exception as e:
        logger.warning("watch_email_failed", error=str(e))


def _run_setup() -> None:
    console.print(
        Panel(
            "[bold]Gmail OAuth2 Setup[/bold]\n\n"
            "1. Go to Google Cloud Console and create OAuth2 credentials\n"
            "2. Download the credentials JSON file\n"
            "3. Save it as [cyan]gmail_credentials.json[/cyan] in your project root\n"
            "4. Run [bold]nj watch[/bold] — it will open a browser to authenticate\n"
            "5. Token will be cached at [cyan].gmail_token.json[/cyan]\n\n"
            "[dim]Required scope: gmail.readonly[/dim]",
            title="nj watch setup",
            border_style="cyan",
        )
    )
