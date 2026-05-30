from __future__ import annotations

import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_ml(
    config,
    subcommand: str = "status",
    company: str = "",
    role: str = "",
    state: str = "CA",
    year: int = 2024,
    job_id: str | None = None,
    db_path: str = "data/nj.db",
) -> None:
    from nj.db.engine import init_db

    init_db(db_path)

    if subcommand == "train":
        _run_train(db_path)
    elif subcommand == "predict":
        _run_predict(company, role, state, year, db_path)
    elif subcommand == "salary":
        _run_salary(role, state, year, db_path)
    elif subcommand == "semantic":
        _run_semantic(job_id, db_path)
    elif subcommand == "status":
        _run_status(db_path)
    else:
        _show_ml_help()


def _run_train(db_path: str) -> None:
    console.print(
        Panel(
            "[bold]Training ML models on USCIS data[/bold]\n\n"
            "[dim]This trains two models:\n"
            "  1. Sponsorship probability (RandomForest)\n"
            "  2. Salary predictor (GradientBoosting)\n\n"
            "Requires H1B data — run nj intel sync first.[/dim]",
            title="nj ml train",
            border_style="cyan",
        )
    )

    console.print("\n[cyan][ 1/2 ][/cyan] Training sponsorship model...")
    from nj.ml.sponsorship_model import SponsorshipModel

    sponsor_model = SponsorshipModel()
    sponsor_metrics = sponsor_model.train(db_path)

    if sponsor_metrics["success"]:
        auc = sponsor_metrics.get("auc_roc", "N/A")
        console.print(
            f"  [green]✓[/green] Sponsorship model trained\n"
            f"  Samples: {sponsor_metrics['training_samples']:,}  "
            f"AUC-ROC: {auc}\n"
            f"  Top features: "
            f"{', '.join(sponsor_metrics.get('top_features', [])[:5])}"
        )
    else:
        console.print(f"  [red]✗[/red] {sponsor_metrics['error']}")

    console.print("\n[cyan][ 2/2 ][/cyan] Training salary model...")
    from nj.ml.salary_model import SalaryModel

    salary_model = SalaryModel()
    salary_metrics = salary_model.train(db_path)

    if salary_metrics["success"]:
        r2 = salary_metrics.get("r2_score", "N/A")
        sal_range = salary_metrics.get("salary_range", {})
        console.print(
            f"  [green]✓[/green] Salary model trained\n"
            f"  Samples: {salary_metrics['training_samples']:,}  "
            f"R²: {r2}\n"
            f"  Salary range in data: "
            f"${sal_range.get('min', 0):,} – "
            f"${sal_range.get('max', 0):,}"
        )
    else:
        console.print(f"  [red]✗[/red] {salary_metrics['error']}")

    console.print(
        "\n[dim]Models saved to data/models/\n"
        "Run [bold]nj ml predict[/bold] to use them.[/dim]"
    )


def _run_predict(
    company: str,
    role: str,
    state: str,
    year: int,
    db_path: str,
) -> None:
    if not company or not role:
        console.print(
            "[red]Usage:[/red] ml predict --company NAME --role TITLE"
        )
        return

    from nj.ml.sponsorship_model import get_sponsorship_model

    model = get_sponsorship_model()
    result = model.predict(company, role, state, year)

    prob = result["probability"]
    tier = result.get("tier", "UNKNOWN")
    color = "green" if prob >= 0.7 else "yellow" if prob >= 0.45 else "red"

    bar_len = int(prob * 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)

    console.print(
        Panel(
            f"[bold]{company}[/bold] · {role}\n\n"
            f"Sponsorship probability:\n"
            f"  [{color}]{bar}[/{color}] "
            f"[{color}][bold]{prob:.1%}[/bold][/{color}]\n\n"
            f"Tier: [{color}]{tier}[/{color}]\n"
            f"Confidence: {result['confidence']}",
            title="Sponsorship Prediction",
            border_style=color,
        )
    )

    from nj.ml.salary_model import get_salary_model

    salary_model = get_salary_model()
    salary = salary_model.predict(role, state, year)
    if salary.get("predicted_salary"):
        low = salary["range"]["low"]
        high = salary["range"]["high"]
        pred = salary["predicted_salary"]
        console.print(
            f"\n[bold]Salary estimate[/bold] ({role} in {state}):\n"
            f"  ${pred:,}/year [dim](range: ${low:,} – ${high:,})[/dim]"
        )
        if salary.get("state_note"):
            console.print(f"  [dim]{salary['state_note']}[/dim]")


def _run_salary(role: str, state: str, year: int, db_path: str) -> None:
    if not role:
        console.print(
            "[red]Usage:[/red] ml salary --role TITLE "
            "[--state CA] [--year 2024]"
        )
        return

    from nj.ml.salary_model import get_salary_model

    model = get_salary_model()
    result = model.predict(role, state, year)

    if not result.get("predicted_salary"):
        console.print(
            f"[yellow]{result.get('reason', 'Model not trained.')}[/yellow]\n"
            "Run [bold]nj ml train[/bold] first."
        )
        return

    pred = result["predicted_salary"]
    low = result["range"]["low"]
    high = result["range"]["high"]
    cat = result.get("role_category", "")

    note_line = f"\n\n[dim]{result['state_note']}[/dim]" if result.get("state_note") else ""

    console.print(
        Panel(
            f"[bold]{role}[/bold] in {state} ({year})\n\n"
            f"Predicted salary: [green][bold]${pred:,}[/bold][/green]\n"
            f"Range:            ${low:,} – ${high:,}\n"
            f"Role category:    {cat}\n"
            f"Confidence:       {result['confidence']}"
            + note_line,
            title="Salary Prediction",
            border_style="green",
        )
    )


def _run_semantic(job_id: str | None, db_path: str) -> None:
    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print("[red]cv/cv_base.json not found.[/red]")
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    if not job_id:
        console.print("[red]Usage:[/red] ml semantic --job-id ID")
        return

    from nj.db.repos.job_repo import JobRepo

    job_repo = JobRepo(db_path)
    jobs = job_repo.get_jobs()
    job = next((j for j in jobs if j.id.startswith(job_id)), None)
    if not job:
        console.print(f"[red]Job '{job_id}' not found.[/red]")
        return

    console.print("[dim]Computing semantic similarity...[/dim]")
    from nj.ml.semantic_model import get_semantic_model

    model = get_semantic_model()
    result = model.score_cv_jd(cv_base, job.description)

    if result.get("semantic_score") is None:
        console.print(f"[yellow]{result.get('reason')}[/yellow]")
        return

    score = result["semantic_score"]
    color = "green" if score >= 70 else "yellow" if score >= 50 else "red"

    console.print(
        Panel(
            f"[bold]{job.title}[/bold] @ {job.company}\n\n"
            f"Semantic match: [{color}][bold]{score}/100[/bold][/{color}]\n"
            f"Interpretation: {result['interpretation']}",
            title="Semantic Similarity",
            border_style=color,
        )
    )

    if result.get("section_scores"):
        console.print(Rule("[dim]Section scores[/dim]"))
        for section, sec_score in sorted(
            result["section_scores"].items(), key=lambda x: x[1], reverse=True
        ):
            bar_len = int(sec_score / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            sec_color = (
                "green" if sec_score >= 70 else "yellow" if sec_score >= 50 else "red"
            )
            console.print(
                f"  [dim]{section:<14}[/dim] [{sec_color}]{bar}[/{sec_color}] {sec_score}"
            )

    gaps = model.find_semantic_gaps(cv_base, job.description)
    if gaps:
        console.print(Rule("[dim]Semantic gaps (JD requirements not in CV)[/dim]"))
        for g in gaps:
            sev_color = "red" if g["gap_severity"] == "high" else "yellow"
            console.print(
                f"  [{sev_color}][{g['gap_severity']}][/{sev_color}] "
                f"{g['jd_requirement'][:80]}"
            )


def _run_status(db_path: str) -> None:
    from nj.ml.sponsorship_model import MODEL_PATH as SPONSOR_PATH
    from nj.ml.salary_model import MODEL_PATH as SALARY_PATH

    console.print(
        Panel(
            "[bold]nj ML Models[/bold]\n\n"
            + _model_status(
                "Sponsorship classifier",
                SPONSOR_PATH,
                "RandomForest on USCIS H1B data",
            )
            + "\n"
            + _model_status(
                "Salary predictor",
                SALARY_PATH,
                "GradientBoosting on wage data",
            )
            + "\n"
            + _semantic_status()
            + "\n\n[dim]Run [bold]nj ml train[/bold] "
            "to train models (requires nj intel sync)[/dim]",
            title="nj ml status",
            border_style="cyan",
        )
    )


def _model_status(name: str, path: Path, description: str) -> str:
    if path.exists():
        size_kb = path.stat().st_size // 1024
        return (
            f"[green]✓[/green] [bold]{name}[/bold] "
            f"[dim]({size_kb}KB — {description})[/dim]"
        )
    return (
        f"[red]✗[/red] [bold]{name}[/bold] "
        f"[dim]not trained — {description}[/dim]"
    )


def _semantic_status() -> str:
    try:
        import sentence_transformers  # noqa: F401

        return (
            "[green]✓[/green] [bold]Semantic model[/bold] "
            "[dim](sentence-transformers installed)[/dim]"
        )
    except ImportError:
        return (
            "[yellow]~[/yellow] [bold]Semantic model[/bold] "
            "[dim](pip install sentence-transformers to enable)[/dim]"
        )


def _show_ml_help() -> None:
    console.print(
        Panel(
            "[bold]nj ml — Machine Learning Models[/bold]\n\n"
            "Commands:\n"
            "  [cyan]nj ml status[/cyan]                  model status\n"
            "  [cyan]nj ml train[/cyan]                   train on USCIS data\n"
            "  [cyan]nj ml predict --company G --role ML[/cyan]  sponsorship probability\n"
            "  [cyan]nj ml salary --role 'ML Engineer' --state CA[/cyan]  salary estimate\n"
            "  [cyan]nj ml semantic --job-id ID[/cyan]    semantic CV-JD similarity\n\n"
            "[dim]Requires: nj intel sync (for train/predict/salary)\n"
            "Optional: pip install sentence-transformers (for semantic)[/dim]",
            border_style="cyan",
        )
    )
