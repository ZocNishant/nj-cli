from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from nj.models.cv import CareerField, VisaStatus
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

_DEFAULT_ROLES: dict[str, list[str]] = {
    "ml_ai": ["ML Engineer", "AI Engineer", "Applied Scientist"],
    "software_engineering": ["Software Engineer", "Backend Engineer", "Full-Stack Engineer"],
    "data_science": ["Data Scientist", "Data Analyst", "Analytics Engineer"],
    "product": ["Product Manager", "APM", "Senior PM"],
    "design": ["UX Designer", "Product Designer", "UI Designer"],
    "research": ["Research Scientist", "Research Engineer", "AI Researcher"],
    "devops_infra": ["DevOps Engineer", "Platform Engineer", "SRE"],
    "cybersecurity": ["Security Engineer", "Penetration Tester", "SOC Analyst"],
    "finance_quant": ["Quantitative Analyst", "Quantitative Developer", "Risk Analyst"],
    "other": ["Software Engineer", "Data Analyst"],
}

_SPONSORSHIP_STATUSES = [
    s.value for s in VisaStatus
    if s not in (VisaStatus.NOT_APPLICABLE, VisaStatus.CITIZEN, VisaStatus.PERMANENT_RESIDENT)
]


def run_init(config_path: str = "config.yaml", force: bool = False) -> None:
    if not force and Path(config_path).exists():
        overwrite = Confirm.ask(
            "[yellow]nj is already initialized.[/yellow] "
            "Re-run setup and overwrite existing config?"
        )
        if not overwrite:
            console.print("[dim]Aborted. Use [bold]nj config[/bold] to edit settings.[/dim]")
            return

    console.print(
        Panel(
            "[bold]Welcome to nj[/bold] — AI Career Operating System\n\n"
            "This wizard will set up:\n"
            "  • Anthropic API key (for AI scoring + tailoring)\n"
            "  • Personal profile (name, location, contact)\n"
            "  • Career field and target roles\n"
            "  • Visa / work authorization\n"
            "  • Your CV base file\n"
            "  • Job search preferences\n"
            "  • Email notifications (optional)\n\n"
            "[dim]Your config is saved locally and never committed to git.[/dim]",
            title="nj init",
            border_style="cyan",
        )
    )

    env = _load_env()
    config_data: dict = {}

    console.print("\n[bold cyan]Step 1 — Anthropic API key[/bold cyan]")
    api_key = _step_api(env)
    env["ANTHROPIC_API_KEY"] = api_key
    config_data["llm"] = {
        "provider": "claude",
        "model": "claude-sonnet-4-20250514",
        "api_key": api_key,
    }

    console.print("\n[bold cyan]Step 2 — Personal info[/bold cyan]")
    personal = _step_personal()

    console.print("\n[bold cyan]Step 3 — Career profile[/bold cyan]")
    career = _step_career()

    console.print("\n[bold cyan]Step 4 — Visa / work authorization[/bold cyan]")
    visa = _step_visa()
    config_data["visa"] = visa

    console.print("\n[bold cyan]Step 5 — CV setup[/bold cyan]")
    _step_cv(api_key, personal, career, visa)

    console.print("\n[bold cyan]Step 6 — Job search preferences[/bold cyan]")
    prefs = _step_preferences(career)
    config_data["search"] = {
        "roles": career["target_roles"],
        "primary_region": career["target_country"],
        "include_global": career.get("include_global", False),
        **prefs,
    }

    console.print("\n[bold cyan]Step 7 — Notifications (optional)[/bold cyan]")
    notify = _step_notifications(env)
    config_data["notify"] = notify

    config_data["scoring"] = {"threshold": 62}
    config_data["apply"] = {
        "enabled": False,
        "max_per_day": 5,
        "automation_phase": 1,
    }
    config_data["schedule"] = {"enabled": False, "every_days": 3, "time": "08:00"}

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


def _step_api(env: dict) -> str:
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
        if _test_api_key(key.strip()):
            console.print("[green]Connected.[/green]")
            return key.strip()
        else:
            console.print("[red]Failed.[/red] Check your key and try again.")


def _step_personal() -> dict:
    console.print("[dim]Enter your contact information.[/dim]")
    name = Prompt.ask("Full name")
    email = Prompt.ask("Email address")
    phone = Prompt.ask("Phone number [dim](optional, press Enter to skip)[/dim]", default="")
    location = Prompt.ask(
        "City, Country [dim](e.g. San Francisco, USA)[/dim]", default=""
    )
    linkedin = Prompt.ask("LinkedIn URL [dim](optional)[/dim]", default="")
    github = Prompt.ask("GitHub URL [dim](optional)[/dim]", default="")
    website = Prompt.ask("Personal website [dim](optional)[/dim]", default="")
    graduation_date = Prompt.ask(
        "Graduation date [dim](e.g. May 2025, leave blank if not applicable)[/dim]",
        default="",
    )
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
        "website": website,
        "graduation_date": graduation_date,
    }


def _step_career() -> dict:
    fields = [f.value for f in CareerField]
    console.print(f"[dim]Available fields: {', '.join(fields)}[/dim]")
    field = Prompt.ask(
        "Career field",
        choices=fields,
        default="software_engineering",
    )
    seniority = Prompt.ask(
        "Seniority level",
        choices=["junior", "mid", "senior", "staff"],
        default="mid",
    )
    default_roles = _DEFAULT_ROLES.get(field, ["Software Engineer"])
    console.print(f"[dim]Suggested roles for {field}: {', '.join(default_roles)}[/dim]")
    custom = Confirm.ask("Customise target roles?", default=False)
    if custom:
        roles_raw = Prompt.ask("Enter roles (comma-separated)")
        roles = [r.strip() for r in roles_raw.split(",") if r.strip()]
    else:
        roles = default_roles
    target_country = Prompt.ask("Primary target country", default="USA")
    include_global = Confirm.ask("Also search globally?", default=False)
    return {
        "career_field": field,
        "seniority": seniority,
        "target_roles": roles,
        "target_country": target_country,
        "include_global": include_global,
    }


def _step_visa() -> dict:
    needs_sponsorship = Confirm.ask(
        "Do you need visa sponsorship for your target country?",
        default=False,
    )
    if not needs_sponsorship:
        return {
            "enabled": False,
            "status": VisaStatus.NOT_APPLICABLE,
            "work_authorization": "Authorized to work",
        }

    status = Prompt.ask(
        "Work authorization status",
        choices=_SPONSORSHIP_STATUSES,
        default="opt",
    )
    h1b = Confirm.ask("Will you need H1B sponsorship in the future?", default=True)
    skip_no_sponsor = Confirm.ask(
        "Auto-skip jobs that say 'no sponsorship'?", default=True
    )
    work_auth_default = (
        f"{status.upper()} — open to H1B sponsorship" if h1b else f"{status.upper()}"
    )
    work_auth = Prompt.ask(
        "Work authorization note [dim](used in cover letters)[/dim]",
        default=work_auth_default,
    )
    return {
        "enabled": True,
        "status": status,
        "h1b_future": h1b,
        "skip_no_sponsorship": skip_no_sponsor,
        "work_authorization": work_auth,
        "include_keywords": ["OPT", "CPT", "H1B", "visa sponsorship", "sponsor"],
        "exclude_keywords": [
            "no sponsorship",
            "citizen only",
            "green card only",
            "must be authorized",
            "no visa",
        ],
    }


def _step_cv(api_key: str, personal: dict, career: dict, visa: dict) -> None:
    cv_path = Path("cv/cv_base.json")
    if cv_path.exists():
        console.print("[green]Found cv/cv_base.json[/green]")
        return

    cv_path.parent.mkdir(parents=True, exist_ok=True)
    console.print(
        "cv/cv_base.json not found.\n"
        "Options:\n"
        "  1. Provide path to your CV PDF (AI will extract it)\n"
        "  2. Start with a blank template\n"
    )
    choice = Prompt.ask("Choice", choices=["1", "2"], default="2")

    if choice == "1":
        pdf_path = Prompt.ask("Path to your CV PDF")
        if Path(pdf_path).exists():
            console.print("[dim]Extracting CV with AI...[/dim]")
            _extract_cv_from_pdf(pdf_path, api_key, personal, career, visa)
        else:
            console.print(f"[red]File not found: {pdf_path}[/red]")
            _build_blank_cv(personal, career, visa, cv_path)
    else:
        _build_blank_cv(personal, career, visa, cv_path)
        console.print(
            "[yellow]Blank CV created at cv/cv_base.json[/yellow]\n"
            "[dim]Edit it with your real information before running nj search.[/dim]"
        )


def _build_blank_cv(personal: dict, career: dict, visa: dict, cv_path: Path) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d")
    cv = {
        "personal": {
            "name": personal.get("name", ""),
            "email": personal.get("email", ""),
            "phone": personal.get("phone", ""),
            "location": personal.get("location", ""),
            "linkedin": personal.get("linkedin", ""),
            "github": personal.get("github", ""),
            "website": personal.get("website", ""),
            "visa_status": visa.get("status", "not_applicable"),
            "work_authorization": visa.get("work_authorization", ""),
            "graduation_date": personal.get("graduation_date", ""),
            "target_country": career.get("target_country", "USA"),
        },
        "career_field": career.get("career_field", "software_engineering"),
        "target_roles": career.get("target_roles", []),
        "target_locations": [],
        "seniority": career.get("seniority", "mid"),
        "summary": "",
        "skills": {},
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "publications": [],
        "languages": [],
        "research_interests": [],
        "soft_skills": [],
        "cv_version": "1.0",
        "created_at": now,
        "last_updated": now,
    }
    with open(cv_path, "w") as f:
        json.dump(cv, f, indent=2)
    console.print("[green]Created cv/cv_base.json[/green]")


def _extract_cv_from_pdf(
    pdf_path: str,
    api_key: str,
    personal: dict,
    career: dict,
    visa: dict,
) -> None:
    try:
        import base64

        import anthropic

        cv_path = Path("cv/cv_base.json")
        with open(pdf_path, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

        client = anthropic.Anthropic(api_key=api_key)
        schema_str = json.dumps({
            "personal": {
                "name": "", "email": "", "phone": "", "location": "",
                "linkedin": "", "github": "", "website": "",
                "visa_status": "not_applicable", "work_authorization": "",
                "graduation_date": "", "target_country": "USA",
            },
            "career_field": "software_engineering",
            "target_roles": [],
            "target_locations": [],
            "seniority": "mid",
            "summary": "",
            "skills": {},
            "experience": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "publications": [],
            "languages": [],
            "research_interests": [],
            "soft_skills": [],
            "cv_version": "1.0",
            "created_at": "",
            "last_updated": "",
        }, indent=2)

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
                                "Extract this CV/resume into the following JSON schema. "
                                "Return ONLY valid JSON, no other text.\n\n"
                                f"Schema:\n{schema_str}"
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

        if "personal" not in cv_data:
            cv_data["personal"] = {}
        for k, v in {
            "visa_status": visa.get("status", "not_applicable"),
            "work_authorization": visa.get("work_authorization", ""),
            "target_country": career.get("target_country", "USA"),
        }.items():
            if not cv_data["personal"].get(k):
                cv_data["personal"][k] = v

        if not cv_data.get("career_field"):
            cv_data["career_field"] = career.get("career_field", "software_engineering")
        if not cv_data.get("target_roles"):
            cv_data["target_roles"] = career.get("target_roles", [])
        if not cv_data.get("seniority"):
            cv_data["seniority"] = career.get("seniority", "mid")

        now = datetime.utcnow().strftime("%Y-%m-%d")
        cv_data.setdefault("cv_version", "1.0")
        cv_data["created_at"] = now
        cv_data["last_updated"] = now

        with open(cv_path, "w") as f:
            json.dump(cv_data, f, indent=2)
        console.print("[green]CV extracted and saved to cv/cv_base.json[/green]")
        console.print("[dim]Review it before running nj search.[/dim]")
    except Exception as e:
        logger.error("cv_extraction_failed", error=str(e))
        console.print(f"[red]CV extraction failed:[/red] {e}")
        _build_blank_cv(personal, career, visa, Path("cv/cv_base.json"))


def _step_preferences(career: dict) -> dict:
    console.print("[dim]Fine-tune your job search filters.[/dim]")
    exclude_raw = Prompt.ask(
        "Keywords to exclude from job titles [dim](comma-separated)[/dim]",
        default="10+ years, Staff Engineer, Principal Engineer",
    )
    keywords_exclude = [k.strip() for k in exclude_raw.split(",") if k.strip()]
    return {"keywords_exclude": keywords_exclude}


def _step_notifications(env: dict) -> dict:
    want_notify = Confirm.ask("Set up email notifications?", default=False)
    if not want_notify:
        return {"email_to": "", "provider": "smtp"}

    provider = Prompt.ask(
        "Email provider",
        choices=["smtp", "sendgrid"],
        default="smtp",
    )
    email_to = Prompt.ask("Send notifications to (your email)")

    if provider == "smtp":
        host = Prompt.ask("SMTP host", default="smtp.gmail.com")
        port = int(Prompt.ask("SMTP port", default="587"))
        user = Prompt.ask("SMTP username")
        password = Prompt.ask(
            "SMTP password [dim](Gmail: use App Password)[/dim]",
            password=True,
        )
        env.update({
            "SMTP_HOST": host,
            "SMTP_PORT": str(port),
            "SMTP_USER": user,
            "SMTP_PASSWORD": password,
        })
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


def _test_api_key(api_key: str) -> bool:
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
        logger.warning("api_key_test_failed", error=str(e))
        return False


def _test_anthropic(api_key: str) -> bool:
    """Backward-compatible alias for _test_api_key."""
    return _test_api_key(api_key)


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
    lines = [f"{k}={v}" for k, v in env.items()]
    Path(".env").write_text("\n".join(lines) + "\n")
    console.print("[dim].env written.[/dim]")


def _write_config(data: dict, path: str) -> None:
    import yaml

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    console.print(f"[dim]{path} written.[/dim]")
