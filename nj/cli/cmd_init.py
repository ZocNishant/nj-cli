from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_init(config_path: str = "config.yaml") -> None:
    if Path(config_path).exists():
        overwrite = Confirm.ask(
            "[yellow]nj is already initialized.[/yellow] "
            "Re-run setup and overwrite existing config?"
        )
        if not overwrite:
            console.print(
                "[dim]Aborted. Use [bold]nj config[/bold] to edit settings.[/dim]"
            )
            return

    console.print(
        Panel(
            "[bold]Welcome to nj[/bold] — AI-powered job hunting CLI\n\n"
            "This wizard will set up:\n"
            "  • Anthropic API key (for AI scoring + tailoring)\n"
            "  • Email notifications (SMTP or SendGrid)\n"
            "  • Your CV base file\n"
            "  • Job search preferences\n"
            "  • Visa / work auth settings\n"
            "  • Run schedule\n\n"
            "[dim]Your config is saved locally and never committed to git.[/dim]",
            title="nj init",
            border_style="cyan",
        )
    )

    env = _load_env()
    config_data: dict = {}

    console.print("\n[bold cyan]Step 1 — Anthropic API key[/bold cyan]")
    api_key = _setup_anthropic(env)
    env["ANTHROPIC_API_KEY"] = api_key
    config_data["llm"] = {
        "provider": "claude",
        "model": "claude-sonnet-4-20250514",
        "api_key": api_key,
    }

    console.print("\n[bold cyan]Step 2 — Email notifications[/bold cyan]")
    notify_config = _setup_email(env)
    config_data["notify"] = notify_config

    console.print("\n[bold cyan]Step 3 — CV setup[/bold cyan]")
    _setup_cv(api_key)

    console.print(
        "\n[bold cyan]Step 4 — LinkedIn session cookie (optional)[/bold cyan]"
    )
    li_at = _setup_linkedin(env)
    if li_at:
        env["LINKEDIN_LI_AT"] = li_at

    console.print("\n[bold cyan]Step 5 — Job search preferences[/bold cyan]")
    search_config = _setup_search()
    config_data["search"] = search_config

    console.print("\n[bold cyan]Step 6 — Visa / work authorization[/bold cyan]")
    visa_config = _setup_visa()
    config_data["visa"] = visa_config

    console.print("\n[bold cyan]Step 7 — Run schedule[/bold cyan]")
    schedule_config = _setup_schedule()
    config_data["schedule"] = schedule_config

    config_data["scoring"] = {"threshold": 62}
    config_data["apply"] = {
        "enabled": False,
        "max_per_day": 5,
        "automation_phase": 1,
    }

    _write_env(env)
    _write_config(config_data, config_path)

    console.print(
        Panel(
            "[green]nj is ready![/green]\n\n"
            "Next steps:\n"
            "  1. [bold]nj search[/bold]       — find and score jobs\n"
            "  2. [bold]nj review[/bold]       — review scored jobs\n"
            "  3. [bold]nj calibrate[/bold]    — tune your score threshold\n"
            "  4. Set [bold]apply.enabled: true[/bold] in config.yaml when ready\n"
            "  5. [bold]nj run[/bold]          — full pipeline\n\n"
            "[dim]Config saved to config.yaml\n"
            "Secrets saved to .env[/dim]",
            title="Setup complete",
            border_style="green",
        )
    )


def _setup_anthropic(env: dict) -> str:
    existing = env.get("ANTHROPIC_API_KEY", "")
    if existing:
        console.print(f"[dim]Found existing API key: {existing[:8]}...[/dim]")
        keep = Confirm.ask("Keep existing key?", default=True)
        if keep:
            return existing

    while True:
        key = Prompt.ask("Anthropic API key [dim](sk-ant-...)[/dim]", password=True)
        if not key.strip():
            console.print("[red]API key cannot be empty.[/red]")
            continue
        console.print("[dim]Testing connection...[/dim]", end=" ")
        if _test_anthropic(key.strip()):
            console.print("[green]Connected.[/green]")
            return key.strip()
        else:
            console.print("[red]Failed.[/red] Check your key and try again.")


def _test_anthropic(api_key: str) -> bool:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply: READY"}],
        )
        return bool(msg.content)
    except Exception as e:
        logger.warning("anthropic_test_failed", error=str(e))
        return False


def _setup_email(env: dict) -> dict:
    provider = Prompt.ask(
        "Email provider",
        choices=["smtp", "sendgrid"],
        default="smtp",
    )
    email_to = Prompt.ask("Send notifications to (your email)")

    if provider == "smtp":
        host = Prompt.ask("SMTP host", default="smtp.gmail.com")
        port = int(Prompt.ask("SMTP port", default="587"))
        user = Prompt.ask("SMTP username (your Gmail address)")
        password = Prompt.ask(
            "SMTP password [dim](Gmail: use App Password, not your login)[/dim]",
            password=True,
        )
        env.update(
            {
                "SMTP_HOST": host,
                "SMTP_PORT": str(port),
                "SMTP_USER": user,
                "SMTP_PASSWORD": password,
            }
        )
        return {
            "email_to": email_to,
            "provider": "smtp",
            "smtp_host": host,
            "smtp_port": port,
            "smtp_user": user,
            "smtp_password": password,
        }
    else:
        sg_key = Prompt.ask("SendGrid API key", password=True)
        env["SENDGRID_API_KEY"] = sg_key
        return {
            "email_to": email_to,
            "provider": "sendgrid",
            "sendgrid_api_key": sg_key,
        }


def _setup_cv(api_key: str) -> None:
    cv_path = Path("cv/cv_base.json")
    if cv_path.exists():
        console.print("[green]Found cv/cv_base.json[/green]")
        return

    cv_path.parent.mkdir(parents=True, exist_ok=True)
    console.print(
        "cv/cv_base.json not found.\n"
        "Options:\n"
        "  1. Provide path to your CV PDF (AI will convert it)\n"
        "  2. Copy cv/cv_base.example.json and edit manually\n"
    )
    choice = Prompt.ask("Choice", choices=["1", "2"], default="2")

    if choice == "1":
        pdf_path = Prompt.ask("Path to your CV PDF")
        if Path(pdf_path).exists():
            console.print("[dim]Extracting and converting CV...[/dim]")
            _convert_pdf_to_cv_base(pdf_path, api_key)
        else:
            console.print(
                f"[red]File not found: {pdf_path}[/red]\n"
                "[yellow]Copy cv_base.example.json manually.[/yellow]"
            )
    else:
        example = Path("cv/cv_base.example.json")
        if example.exists():
            import shutil

            shutil.copy(example, cv_path)
            console.print(
                "[yellow]Copied cv_base.example.json → cv/cv_base.json[/yellow]\n"
                "[dim]Edit it with your real information before running nj search.[/dim]"
            )
        else:
            console.print(
                "[yellow]Create cv/cv_base.json based on cv_base.example.json[/yellow]"
            )


def _convert_pdf_to_cv_base(pdf_path: str, api_key: str) -> None:
    try:
        import base64

        import anthropic

        with open(pdf_path, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")
        client = anthropic.Anthropic(api_key=api_key)
        with open("cv/cv_base.example.json") as f:
            schema = f.read()
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f"Extract this CV into the following JSON schema. "
                                f"Return ONLY valid JSON, no other text.\n\n"
                                f"Schema:\n{schema}"
                            ),
                        },
                    ],
                }
            ],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        cv_data = json.loads(raw)
        with open("cv/cv_base.json", "w") as f:
            json.dump(cv_data, f, indent=2)
        console.print("[green]CV converted and saved to cv/cv_base.json[/green]")
        console.print("[dim]Review it before running nj search.[/dim]")
    except Exception as e:
        logger.error("cv_conversion_failed", error=str(e))
        console.print(
            f"[red]CV conversion failed:[/red] {e}\n"
            "[yellow]Copy cv_base.example.json and edit manually.[/yellow]"
        )


def _setup_linkedin(env: dict) -> str | None:
    existing = env.get("LINKEDIN_LI_AT", "")
    if existing:
        console.print("[dim]Found existing LinkedIn cookie.[/dim]")
        keep = Confirm.ask("Keep existing cookie?", default=True)
        if keep:
            return None

    console.print(
        "To scrape LinkedIn you need your session cookie.\n"
        "[dim]How to get it:\n"
        "  1. Open LinkedIn in Chrome and log in\n"
        "  2. Press F12 → Application tab → Cookies → linkedin.com\n"
        "  3. Find 'li_at' and copy its value[/dim]"
    )
    skip = Confirm.ask("Skip LinkedIn setup? (Indeed only)", default=False)
    if skip:
        console.print("[yellow]LinkedIn scraper disabled. " "Indeed only.[/yellow]")
        return None

    cookie = Prompt.ask("li_at cookie value", password=True)
    return cookie.strip() if cookie.strip() else None


def _setup_search() -> dict:
    console.print(
        "[dim]Default roles: ML Engineer, Computer Vision Engineer, "
        "AI Engineer[/dim]"
    )
    custom = Confirm.ask("Customise target roles?", default=False)
    if custom:
        roles_raw = Prompt.ask("Enter roles (comma-separated)")
        roles = [r.strip() for r in roles_raw.split(",") if r.strip()]
    else:
        roles = ["ML Engineer", "Computer Vision Engineer", "AI Engineer"]

    region = Prompt.ask("Primary region", default="USA")
    global_search = Confirm.ask("Also search globally?", default=False)
    return {
        "roles": roles,
        "primary_region": region,
        "include_global": global_search,
        "keywords_exclude": ["10+ years", "Staff Engineer", "Principal Engineer"],
    }


def _setup_visa() -> dict:
    has_visa_needs = Confirm.ask(
        "Are you an international student or need visa sponsorship?",
        default=True,
    )
    if not has_visa_needs:
        return {"enabled": False}

    status = Prompt.ask(
        "Work authorization status",
        choices=["OPT", "CPT", "H1B", "GC", "citizen"],
        default="OPT",
    )
    h1b = Confirm.ask("Seeking H1B sponsorship in future?", default=True)
    skip_no_sponsor = Confirm.ask(
        "Auto-skip jobs that say 'no sponsorship'?", default=True
    )
    return {
        "enabled": True,
        "status": status,
        "h1b_future": h1b,
        "skip_no_sponsorship": skip_no_sponsor,
        "include_keywords": ["OPT", "CPT", "H1B", "visa sponsorship", "sponsor"],
        "exclude_keywords": [
            "no sponsorship",
            "citizen only",
            "green card only",
            "must be authorized",
            "no visa",
        ],
    }


def _setup_schedule() -> dict:
    console.print("[dim]nj can run automatically on a schedule.[/dim]")
    schedule = Confirm.ask("Set up automatic schedule?", default=True)
    if not schedule:
        return {"enabled": False, "every_days": 3, "time": "08:00"}

    days = Prompt.ask(
        "Run every N days [dim](1=daily, 3=every 3 days)[/dim]",
        default="3",
    )
    try:
        days_int = max(1, int(days))
    except ValueError:
        days_int = 3

    time_str = Prompt.ask("Run at time (HH:MM)", default="08:00")
    return {
        "enabled": True,
        "every_days": days_int,
        "time": time_str,
    }


def _load_env() -> dict:
    env: dict = {}
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _write_env(env: dict) -> None:
    lines = []
    for k, v in env.items():
        lines.append(f"{k}={v}")
    Path(".env").write_text("\n".join(lines) + "\n")
    console.print("[dim].env written.[/dim]")


def _write_config(data: dict, path: str) -> None:
    import yaml

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    console.print(f"[dim]{path} written.[/dim]")
