from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from nj.db.repos.job_repo import JobRepo
from nj.db.repos.score_repo import ScoreRepo
from nj.models.config import Config
from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_explain(
    config: Config,
    job_id: str | None = None,
    db_path: str = "data/nj.db",
    top_n: int = 5,
) -> None:
    job_repo = JobRepo(db_path)
    score_repo = ScoreRepo(db_path)

    if not job_id:
        _show_top_jobs(job_repo, score_repo, top_n)
        return

    jobs = job_repo.get_jobs()
    job = next((j for j in jobs if j.id == job_id), None)
    if not job:
        job = next(
            (j for j in jobs if j.id.startswith(job_id)),
            None,
        )
    if not job:
        console.print(
            f"[red]Job '{job_id}' not found.[/red]\n"
            "Run [bold]nj explain[/bold] to see all scored jobs."
        )
        return

    score = score_repo.get_score(job.id)
    if not score:
        console.print(
            "[yellow]No score found for this job.[/yellow]\n"
            "Run [bold]nj search[/bold] to score jobs first."
        )
        return

    from nj.db.repos.enrichment_repo import EnrichmentRepo

    enrichment_repo = EnrichmentRepo(db_path)
    enrichment = enrichment_repo.get_enrichment(job.id)
    _display_full_explanation(job, score)
    _display_enrichment(enrichment)


def _show_top_jobs(job_repo, score_repo, top_n: int) -> None:
    jobs = job_repo.get_jobs()
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow] Run [bold]nj search[/bold] first.")
        return

    scored = []
    for job in jobs:
        score = score_repo.get_score(job.id)
        if score:
            scored.append((job, score))

    if not scored:
        console.print(
            "[yellow]No scored jobs found.[/yellow] Run [bold]nj search[/bold] (without --dry-run)."
        )
        return

    scored.sort(key=lambda x: x[1].total_score, reverse=True)

    table = Table(
        title=f"Scored jobs — top {min(top_n, len(scored))}",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("ID (first 8)", style="dim")
    table.add_column("Score", min_width=5, justify="center")
    table.add_column("Confidence", justify="center")
    table.add_column("Visa")
    table.add_column("Company")
    table.add_column("Role")
    table.add_column("Status")

    for job, score in scored[:top_n]:
        s = score.total_score
        color = "green" if s >= 75 else "yellow" if s >= 60 else "red"
        visa_color = (
            "green"
            if job.visa_label.value == "confirmed"
            else "yellow"
            if job.visa_label.value == "likely"
            else "red"
            if job.visa_label.value == "blocked"
            else "dim"
        )
        table.add_row(
            job.id[:8],
            f"[{color}]{s}[/{color}]",
            f"{score.confidence:.2f}",
            f"[{visa_color}]{job.visa_label.value}[/{visa_color}]",
            job.company[:22],
            job.title[:30],
            job.status.value[:14],
        )

    console.print(table)
    console.print(
        "\n[dim]Run [bold]nj explain --job-id ID[/bold] for full explanation of any job.[/dim]"
    )


def _display_full_explanation(job, score) -> None:
    total = score.total_score
    color = "green" if total >= 75 else "yellow" if total >= 60 else "red"

    console.print(
        Panel(
            f"[bold]{job.title}[/bold] @ "
            f"[cyan]{job.company}[/cyan]\n"
            f"[dim]{job.location} · {job.source} · "
            f"visa: {job.visa_label.value}[/dim]\n\n"
            f"Score: [{color}][bold]{total}/100[/bold][/{color}]  "
            f"Confidence: {score.confidence:.2f}  "
            f"Prompt: [dim]{score.prompt_version}[/dim]\n\n"
            f"[bold]Why:[/bold] {score.overall_rationale}",
            title="nj explain",
            border_style=color,
        )
    )

    if score.sub_scores:
        console.print(Rule("[dim]Score breakdown[/dim]"))
        table = Table(
            box=box.SIMPLE,
            show_header=True,
            pad_edge=False,
        )
        table.add_column("Category", width=26)
        table.add_column("Score", width=8, justify="center")
        table.add_column("Weight", width=8, justify="center")
        table.add_column("Contribution", width=12, justify="center")
        table.add_column("Rationale", width=50)

        for sub in sorted(
            score.sub_scores,
            key=lambda s: s.score,
            reverse=True,
        ):
            s = sub.score
            sc = "green" if s >= 75 else "yellow" if s >= 60 else "red"
            contribution = round(sub.score * sub.weight)
            bar_len = sub.score // 10
            bar = "█" * bar_len + "░" * (10 - bar_len)
            table.add_row(
                sub.category.value.replace("_", " ").title(),
                f"[{sc}]{s}[/{sc}]",
                f"{sub.weight:.0%}",
                f"[{sc}]+{contribution}[/{sc}]",
                sub.rationale[:50],
            )

        console.print(table)

        console.print()
        console.print("[dim]Visual breakdown:[/dim]")
        for sub in sorted(
            score.sub_scores,
            key=lambda s: s.score,
            reverse=True,
        ):
            s = sub.score
            sc = "green" if s >= 75 else "yellow" if s >= 60 else "red"
            bar_len = s // 5
            bar = "█" * bar_len + "░" * (20 - bar_len)
            label = sub.category.value.replace("_", " ").title()
            console.print(f"  [dim]{label:<26}[/dim] [{sc}]{bar}[/{sc}] [{sc}]{s}[/{sc}]")

    if score.sub_scores:
        evidence_items = []
        for sub in score.sub_scores:
            for e in sub.evidence[:2]:
                if e:
                    evidence_items.append(f"[dim]{sub.category.value.split('_')[0]}:[/dim] {e}")
        if evidence_items:
            console.print(Rule("[dim]JD evidence that drove scoring[/dim]"))
            for item in evidence_items[:8]:
                console.print(f"  [green]•[/green] {item}")

    console.print(Rule("[dim]Skill analysis[/dim]"))
    if score.matched_skills:
        matched_str = "  ".join(f"[green]{s}[/green]" for s in score.matched_skills[:8])
        console.print(f"[bold]Matched:[/bold] {matched_str}")
    if score.missing_skills:
        missing_str = "  ".join(f"[red]{s}[/red]" for s in score.missing_skills[:6])
        console.print(f"[bold]Missing:[/bold] {missing_str}")
    if score.recommended_emphasis:
        emphasis_str = ", ".join(score.recommended_emphasis[:4])
        console.print(f"[bold]Lead with:[/bold] [cyan]{emphasis_str}[/cyan]")

    console.print(Rule("[dim]Visa compatibility[/dim]"))
    visa_icon = "✓" if score.visa_compatible else "✗"
    visa_color = "green" if score.visa_compatible else "red"
    console.print(
        f"  [{visa_color}]{visa_icon}[/{visa_color}] "
        f"{score.visa_notes or 'No visa information detected'}"
    )

    console.print(Rule("[dim]Recommendation[/dim]"))
    if total >= 75:
        action = "[green]Strong application — approve in nj review[/green]"
    elif total >= 62:
        action = "[yellow]Moderate fit — review carefully before approving[/yellow]"
    else:
        action = "[red]Below threshold — consider skipping[/red]"

    if score.recommended_emphasis:
        emphasis = score.recommended_emphasis[0]
        action += f"\n  Lead your tailored CV with: [cyan]{emphasis}[/cyan]"

    console.print(f"  {action}")
    console.print(f"\n  [dim]Job ID: {job.id}[/dim]\n  [dim]Run: nj tailor --url {job.url}[/dim]")


def _display_enrichment(enrichment: dict | None) -> None:
    if not enrichment:
        return
    has_data = any(
        [
            enrichment.get("sponsorship"),
            enrichment.get("salary"),
            enrichment.get("uscis_profile"),
            enrichment.get("semantic"),
        ]
    )
    if not has_data:
        return

    console.print(Rule("[dim]Intelligence enrichment[/dim]"))

    sponsor = enrichment.get("sponsorship")
    if sponsor and sponsor.get("probability") is not None:
        prob = sponsor["probability"]
        tier = sponsor.get("tier", "")
        color = "green" if prob >= 0.7 else "yellow" if prob >= 0.45 else "red"
        bar_len = int(prob * 15)
        bar = "█" * bar_len + "░" * (15 - bar_len)
        console.print(
            f"  [dim]ML sponsorship:[/dim] "
            f"[{color}]{bar}[/{color}] "
            f"[{color}]{prob:.1%}[/{color}] "
            f"[dim]{tier}[/dim]"
        )

    uscis = enrichment.get("uscis_profile")
    if uscis and uscis.get("total_petitions", 0) > 0:
        tier = uscis.get("sponsor_tier", "UNKNOWN")
        color = {"STRONG": "green", "MODERATE": "yellow", "WEAK": "red"}.get(tier, "dim")
        approval = uscis.get("approval_rate", 0)
        ml_count = uscis.get("ml_ai_petitions", 0)
        console.print(
            f"  [dim]USCIS data:[/dim]    "
            f"[{color}]{uscis['total_petitions']} petitions[/{color}] · "
            f"[{color}]{approval}% approved[/{color}] · "
            f"[dim]{ml_count} ML roles[/dim]"
        )

    salary = enrichment.get("salary")
    if salary and salary.get("predicted_salary"):
        pred = salary["predicted_salary"]
        rng = salary.get("range") or {}
        low = rng.get("low", 0)
        high = rng.get("high", 0)
        console.print(
            f"  [dim]Salary est:[/dim]    "
            f"[green]${pred:,}[/green] "
            f"[dim](${low:,} – ${high:,})[/dim]"
        )

    semantic = enrichment.get("semantic")
    if semantic and semantic.get("score") is not None:
        score = semantic["score"]
        color = "green" if score >= 70 else "yellow" if score >= 50 else "red"
        console.print(
            f"  [dim]Semantic match:[/dim] "
            f"[{color}]{score}/100[/{color}] "
            f"[dim]{semantic.get('interpretation', '')}[/dim]"
        )
