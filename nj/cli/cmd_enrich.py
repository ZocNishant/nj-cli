from __future__ import annotations

import asyncio
import json
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from nj.models.config import Config
from nj.utils.logger import get_logger

if TYPE_CHECKING:
    from nj.models.job import Job

logger = get_logger(__name__)
console = Console()


def run_enrich(
    config: Config,
    url: str | None = None,
    db_path: str = "data/nj.db",
    no_score: bool = False,
) -> None:
    if not url:
        console.print(
            "[red]Usage:[/red] enrich <url>\nExample: enrich https://jobs.lever.co/company/job-id"
        )
        return

    from nj.db.engine import init_db

    init_db(db_path)

    console.print("\n[dim]Fetching job from URL...[/dim]")

    job = _fetch_job_from_url(url, config)
    if not job:
        console.print("[red]Failed to fetch job.[/red]\nCheck the URL and try again.")
        return

    console.print(
        Panel(
            f"[bold]{job.title}[/bold] @ [cyan]{job.company}[/cyan]\n"
            f"[dim]{job.location} · {job.source}[/dim]",
            title="Job fetched",
            border_style="cyan",
        )
    )

    cv_base = None
    cv_path = Path("cv/cv_base.json")
    if cv_path.exists():
        with open(cv_path) as f:
            cv_base = json.load(f)

    console.print("[dim]Running intelligence layers...[/dim]\n")

    from nj.intel.enrichment import JobEnrichment

    enricher = JobEnrichment(db_path=db_path)
    enrichment = enricher.enrich(job, cv_base)

    _display_enrich_report(job, enrichment, config)

    if not no_score and cv_base:
        import os

        api_key = config.llm.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if api_key:
            console.print("\n[dim]Scoring with Claude...[/dim]")
            _score_and_display(job, cv_base, config)
        else:
            console.print(
                "\n[dim]Skipping AI score — no API key configured.[/dim]\n"
                "Set ANTHROPIC_API_KEY to enable scoring."
            )

    try:
        from nj.db.repos.enrichment_repo import EnrichmentRepo
        from nj.db.repos.job_repo import JobRepo

        job_repo = JobRepo(db_path)
        enrich_repo = EnrichmentRepo(db_path)
        if not job_repo.job_exists(job.id):
            job_repo.save_job(job)
        enrich_repo.save_enrichment(job.id, enrichment)
        console.print(f"[dim]Saved to DB: {job.id[:12]}...[/dim]")
    except Exception as e:
        logger.debug("enrich_save_failed", error=str(e))


def _fetch_job_from_url(url: str, config) -> Job | None:
    from datetime import datetime

    import httpx

    from nj.models.job import Job
    from nj.scoring.visa_filter import VisaFilter
    from nj.utils.text import clean_html, truncate

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers=headers)
        resp.raise_for_status()
        description = truncate(clean_html(resp.text), 4000)
        title, company = _extract_title_company(resp.text, url)
        visa_label = VisaFilter(config.visa).classify(description)
        return Job(
            id=Job.generate_id(company, title, url),
            title=title,
            company=company,
            url=url,
            description=description,
            location="",
            source="direct",
            visa_label=visa_label,
            scraped_at=datetime.now(UTC),
            description_hash=Job.generate_hash(description),
        )
    except Exception as e:
        logger.warning("enrich_fetch_failed", url=url, error=str(e))
        return None


def _extract_title_company(html: str, url: str) -> tuple[str, str]:
    import re
    from urllib.parse import urlparse

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    raw_title = title_match.group(1).strip() if title_match else ""

    title = raw_title
    for separator in [" at ", " | ", " - ", " — "]:
        if separator in title:
            title = title.split(separator)[0].strip()
            break

    company = "Unknown"
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    known_boards = {
        "linkedin.com",
        "lever.co",
        "greenhouse.io",
        "workday.com",
        "jobs.lever.co",
        "boards.greenhouse.io",
    }

    if domain in known_boards:
        path_parts = parsed.path.strip("/").split("/")
        if path_parts:
            company = path_parts[0].replace("-", " ").title()
    else:
        company = domain.split(".")[0].title()

    at_match = re.search(
        r"(?:at|@)\s+([A-Z][^|–\-\n]+?)(?:\s*[|–]|$)",
        raw_title,
    )
    if at_match:
        company = at_match.group(1).strip()

    if not title or len(title) < 3:
        title = "Job from URL"
    if not company or len(company) < 2:
        company = "Company"

    return title[:80], company[:60]


def _display_enrich_report(job, enrichment: dict, config) -> None:
    sponsor = enrichment.get("sponsorship")
    uscis = enrichment.get("uscis_profile")
    salary = enrichment.get("salary")
    semantic = enrichment.get("semantic")

    lines = []

    visa_color = {
        "confirmed": "green",
        "likely": "cyan",
        "unknown": "yellow",
        "blocked": "red",
    }.get(job.visa_label.value, "dim")
    lines.append(f"Visa signal:     [{visa_color}]{job.visa_label.value.upper()}[/{visa_color}]")

    if sponsor and sponsor.get("probability") is not None:
        prob = sponsor["probability"]
        tier = sponsor.get("tier", "")
        color = "green" if prob >= 0.7 else "yellow" if prob >= 0.45 else "red"
        bar_len = int(prob * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(
            f"ML sponsorship:  [{color}]{bar}[/{color}] "
            f"[{color}]{prob:.1%}[/{color}] [dim]{tier}[/dim]"
        )

    if uscis and uscis.get("total_petitions", 0) > 0:
        tier = uscis.get("sponsor_tier", "UNKNOWN")
        color = {"STRONG": "green", "MODERATE": "yellow", "WEAK": "red"}.get(tier, "dim")
        lines.append(
            f"USCIS history:   [{color}]{uscis['total_petitions']} petitions · "
            f"{uscis['approval_rate']}% approved · {tier}[/{color}]"
        )
        if uscis.get("ml_ai_petitions", 0) > 0:
            lines.append(f"ML roles filed:  [cyan]{uscis['ml_ai_petitions']}[/cyan]")
    elif uscis is not None:
        lines.append("[dim]USCIS history:   no data (run nj intel sync)[/dim]")

    if salary and salary.get("predicted_salary"):
        pred = salary["predicted_salary"]
        low = salary["range"]["low"]
        high = salary["range"]["high"]
        lines.append(f"Salary estimate: [green]${pred:,}[/green] [dim](${low:,} – ${high:,})[/dim]")

    if semantic and semantic.get("score") is not None:
        score = semantic["score"]
        color = "green" if score >= 70 else "yellow" if score >= 50 else "red"
        lines.append(
            f"Semantic match:  [{color}]{score}/100[/{color}] "
            f"[dim]{semantic.get('interpretation', '')}[/dim]"
        )

    if lines:
        console.print(Panel("\n".join(lines), title="Intelligence Report", border_style="cyan"))

    if job.description:
        console.print(Rule("[dim]Job description (excerpt)[/dim]"))
        excerpt = job.description[:500]
        suffix = "..." if len(job.description) > 500 else ""
        console.print(f"[dim]{excerpt}{suffix}[/dim]")


def _score_and_display(job, cv_base: dict, config) -> None:
    from nj.providers.registry import get_provider
    from nj.scoring.scorer import score_job

    try:
        provider = get_provider(config.llm, task="scoring")
        result = asyncio.run(
            score_job(job=job, cv_base=cv_base, config=config, provider=provider, repo=None)
        )
        total = result.total_score
        color = "green" if total >= 75 else "yellow" if total >= 60 else "red"
        console.print(
            Panel(
                f"Total score: [{color}][bold]{total}/100[/bold][/{color}]  "
                f"Confidence: {result.confidence:.2f}\n\n"
                f"{result.overall_rationale}\n\n"
                f"[bold]Matched:[/bold] [green]{', '.join(result.matched_skills[:6])}[/green]\n"
                f"[bold]Missing:[/bold] [red]{', '.join(result.missing_skills[:4])}[/red]\n\n"
                f"[bold]Lead with:[/bold] [cyan]{', '.join(result.recommended_emphasis[:3])}[/cyan]",
                title="AI Score",
                border_style=color,
            )
        )
    except Exception as e:
        console.print(f"[yellow]Scoring failed:[/yellow] {e}")
