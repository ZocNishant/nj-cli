from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

TIER_COLORS = {
    "STRONG":  "bold green",
    "MODERATE": "yellow",
    "WEAK":    "red",
    "UNKNOWN": "dim",
}

TIER_ICONS = {
    "STRONG":  "[bold green]+++[/bold green]",
    "MODERATE": "[yellow]++[/yellow]",
    "WEAK":    "[red]+[/red]",
    "UNKNOWN": "[dim]?[/dim]",
}


def _check_data_synced(repo) -> bool:  # type: ignore[type-arg]
    stats = repo.get_stats()
    if stats["total_petitions"] == 0:
        console.print(
            "\n[yellow]No H1B data loaded.[/yellow] "
            "Run [bold]intel sync[/bold] first to download USCIS data.\n"
        )
        return False
    return True


def _show_intel_help() -> None:
    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("Subcommand", style="bold cyan", width=20)
    table.add_column("Description", style="dim")
    table.add_row("sync",    "Download USCIS H1B data (2022–2024)")
    table.add_row("company", "Profile a company's H1B history")
    table.add_row("top",     "Top ML/AI H1B sponsors")
    table.add_row("role",    "Which companies sponsor a role")
    table.add_row("search",  "Search companies by name fragment")
    table.add_row("stats",   "Overall dataset stats")
    console.print(table)
    console.print(
        "[dim]  Examples:\n"
        "    intel company Google\n"
        "    intel top --state CA --limit 10\n"
        "    intel role 'machine learning engineer'\n"
        "    intel search amazon\n"
        "    intel stats[/dim]\n"
    )


def _run_sync(db_path: str, year: int = 0) -> None:
    from nj.intel.pipeline import download_uscis_data, parse_uscis_csv
    from nj.db.repos.intel_repo import IntelRepo

    repo = IntelRepo(db_path)
    years = [2023, 2022, 2021]
    years_to_sync = [year] if year else years

    for y in years_to_sync:
        if repo.petitions_exist_for_year(y):
            console.print(f"  [dim]Year {y}: already loaded — skip[/dim]")
            continue
        console.print(f"  [cyan]Downloading {y} USCIS data...[/cyan]")
        try:
            csv_path = download_uscis_data(y)
            if csv_path is None:
                console.print(f"  [yellow]✗ {y}:[/yellow] data unavailable — skipping")
                continue
            console.print(f"  [dim]Parsing {csv_path.name}...[/dim]")
            records = parse_uscis_csv(csv_path, y)
            count = repo.bulk_insert_petitions(records)
            console.print(f"  [green]✓ {y}:[/green] {count:,} petitions loaded")
        except Exception as e:
            console.print(f"  [red]✗ {y}:[/red] {e}")

    console.print("\n  [cyan]Rebuilding company intelligence index...[/cyan]")
    companies = repo.rebuild_company_intel()
    console.print(f"  [green]✓[/green] {companies:,} companies indexed\n")


def _run_company(company_name: str, db_path: str) -> None:
    from nj.db.repos.intel_repo import IntelRepo

    repo = IntelRepo(db_path)
    if not _check_data_synced(repo):
        return

    profile = repo.get_company_profile(company_name)
    if not profile:
        console.print(
            f"\n[yellow]No data found for:[/yellow] {company_name}\n"
            f"  Try [bold]intel search {company_name.split()[0].lower()}[/bold] "
            f"to find the exact name.\n"
        )
        return

    tier = profile["sponsor_tier"]
    tier_color = TIER_COLORS.get(tier, "dim")
    tier_icon = TIER_ICONS.get(tier, "?")

    console.print()
    console.print(
        Panel(
            f"[bold]{profile['company']}[/bold]",
            subtitle=f"[{tier_color}]{tier}[/{tier_color}] sponsor",
            border_style=tier_color.replace("bold ", ""),
        )
    )

    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("Field", style="dim", width=22)
    table.add_column("Value", style="bold")

    approval_pct = f"{profile['approval_rate']:.1f}%"

    table.add_row("Sponsor tier", f"{tier_icon} {tier}")
    table.add_row("Total employer records", f"{profile['total_petitions']:,}")
    table.add_row("Approved records", f"{profile['approved']:,}")
    table.add_row("Denied records", f"{profile['denied']:,}")
    table.add_row("Approval rate", approval_pct)
    table.add_row(
        "Years active",
        ", ".join(str(y) for y in profile["years_active"]) or "N/A",
    )
    table.add_row(
        "States",
        ", ".join(profile["top_states"][:6]) or "N/A",
    )
    console.print(table)
    console.print()


def _run_top(state: str, year: int, limit: int, db_path: str) -> None:
    from nj.db.repos.intel_repo import IntelRepo

    repo = IntelRepo(db_path)
    if not _check_data_synced(repo):
        return

    results = repo.get_top_ml_sponsors(state=state, year=year, limit=limit)
    if not results:
        console.print("\n[yellow]No results.[/yellow]\n")
        return

    title = "Top ML/AI H1B Sponsors"
    if state:
        title += f" · {state.upper()}"
    if year:
        title += f" · {year}"

    table = Table(title=title, box=box.SIMPLE, show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Company", style="bold", min_width=28)
    table.add_column("Tier", width=10)
    table.add_column("Employer Records", justify="right", width=17)

    for i, r in enumerate(results, 1):
        tier = r["sponsor_tier"]
        tier_str = TIER_ICONS.get(tier, tier)
        table.add_row(
            str(i),
            r["company"],
            tier_str,
            str(r["total_ml_petitions"]),
        )

    console.print()
    console.print(table)
    console.print()


def _run_role(role_query: str, limit: int, db_path: str) -> None:
    from nj.db.repos.intel_repo import IntelRepo

    repo = IntelRepo(db_path)
    if not _check_data_synced(repo):
        return

    results = repo.get_role_sponsorship(role_query, limit=limit)
    if not results:
        console.print(f"\n[yellow]No sponsorship data for:[/yellow] {role_query}\n")
        return

    table = Table(
        title=f"H1B Sponsors for '{role_query}'",
        box=box.SIMPLE,
        show_header=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Employer", style="bold", min_width=28)
    table.add_column("Petitions", justify="right", width=10)
    table.add_column("Avg Salary", justify="right", width=11)

    for i, r in enumerate(results, 1):
        salary = f"${r['avg_salary']:,.0f}" if r.get("avg_salary") else "N/A"
        table.add_row(str(i), r["employer"], str(r["petitions"]), salary)

    console.print()
    console.print(table)
    console.print()


def _run_search(query: str, db_path: str) -> None:
    from nj.db.repos.intel_repo import IntelRepo

    repo = IntelRepo(db_path)
    if not _check_data_synced(repo):
        return

    results = repo.search_company(query)
    if not results:
        console.print(f"\n[yellow]No companies matching:[/yellow] {query}\n")
        return

    table = Table(
        title=f"Companies matching '{query}'",
        box=box.SIMPLE,
        show_header=True,
    )
    table.add_column("Company", style="bold", min_width=28)
    table.add_column("Tier", width=10)
    table.add_column("Petitions", justify="right", width=10)
    table.add_column("ML/AI", justify="right", width=7)
    table.add_column("Approval %", justify="right", width=11)

    for r in results:
        tier_str = TIER_ICONS.get(r["sponsor_tier"], r["sponsor_tier"])
        approval = f"{r['approval_rate'] * 100:.0f}%"
        table.add_row(
            r["name"],
            tier_str,
            str(r["total_petitions"]),
            str(r["ml_ai_petitions"]),
            approval,
        )

    console.print()
    console.print(table)
    console.print()


def _run_stats(db_path: str) -> None:
    from nj.db.repos.intel_repo import IntelRepo

    repo = IntelRepo(db_path)
    stats = repo.get_stats()

    if stats["total_petitions"] == 0:
        console.print("\n[yellow]No H1B data loaded.[/yellow] Run [bold]intel sync[/bold] first.\n")
        return

    console.print()
    console.print(
        Panel(
            f"[bold cyan]{stats['total_petitions']:,}[/bold cyan] total petitions\n"
            f"[bold green]{stats['ml_petitions']:,}[/bold green] ML/AI petitions "
            f"({stats['ml_petitions'] / max(stats['total_petitions'], 1) * 100:.1f}%)\n"
            f"Years: [dim]{', '.join(str(y) for y in stats['years'])}[/dim]",
            title="H1B Intelligence Stats",
            border_style="cyan",
        )
    )
    console.print()


def run_intel(
    subcommand: str | None = None,
    query: str = "",
    state: str = "",
    year: int = 0,
    limit: int = 20,
    db_path: str = "data/nj.db",
) -> None:
    if not subcommand or subcommand == "help":
        _show_intel_help()
        return

    sub = subcommand.lower()

    if sub == "sync":
        _run_sync(db_path, year=year)
    elif sub == "company":
        if not query:
            console.print("[red]Usage:[/red] intel company <company name>")
            return
        _run_company(query, db_path)
    elif sub == "top":
        _run_top(state=state, year=year, limit=limit, db_path=db_path)
    elif sub == "role":
        if not query:
            console.print("[red]Usage:[/red] intel role <role query>")
            return
        _run_role(query, limit=limit, db_path=db_path)
    elif sub == "search":
        if not query:
            console.print("[red]Usage:[/red] intel search <company fragment>")
            return
        _run_search(query, db_path)
    elif sub == "stats":
        _run_stats(db_path)
    else:
        console.print(f"[red]Unknown intel subcommand:[/red] {sub}")
        _show_intel_help()
