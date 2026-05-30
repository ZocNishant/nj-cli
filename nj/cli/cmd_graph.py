from __future__ import annotations

import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.tree import Tree

from nj.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_graph(
    config,
    subcommand: str = "stats",
    query: str = "",
    target: str = "",
    db_path: str = "data/nj.db",
) -> None:
    from nj.db.engine import init_db

    init_db(db_path)

    if subcommand == "build":
        _run_build(db_path)
    elif subcommand == "stats":
        _run_stats(db_path)
    elif subcommand == "show":
        _run_show(db_path)
    elif subcommand == "path":
        _run_path(query, target, db_path)
    elif subcommand == "skills":
        _run_skills(db_path)
    elif subcommand == "companies":
        _run_companies(db_path)
    else:
        _show_graph_help()


def _run_build(db_path: str) -> None:
    cv_path = Path("cv/cv_base.json")
    if not cv_path.exists():
        console.print("[red]cv/cv_base.json not found.[/red]")
        return

    with open(cv_path) as f:
        cv_base = json.load(f)

    from nj.graph.builder import GraphBuilder

    builder = GraphBuilder(db_path)

    console.print("[dim]Building career graph from CV...[/dim]")
    cv_counts = builder.build_from_cv(cv_base)

    console.print("[dim]Enriching from job scores...[/dim]")
    score_counts = builder.build_from_scores(db_path)

    console.print(
        Panel(
            f"[green]Career graph built.[/green]\n\n"
            f"From CV:     {cv_counts['nodes']} nodes  "
            f"{cv_counts['edges']} edges\n"
            f"From scores: {score_counts['nodes']} nodes  "
            f"{score_counts['edges']} edges\n\n"
            f"[dim]Run [bold]nj graph show[/bold] to visualize[/dim]",
            title="nj graph build",
            border_style="green",
        )
    )


def _run_stats(db_path: str) -> None:
    from nj.graph.repo import GraphRepo

    repo = GraphRepo(db_path)
    stats = repo.get_graph_stats()

    if stats["total_nodes"] == 0:
        console.print(
            "[yellow]Career graph is empty.[/yellow]\n"
            "Run [bold]nj graph build[/bold] to populate it."
        )
        return

    console.print(
        Panel(
            f"[bold]Career Knowledge Graph[/bold]\n\n"
            f"Total nodes: [cyan]{stats['total_nodes']}[/cyan]\n"
            f"Total edges: [cyan]{stats['total_edges']}[/cyan]",
            title="nj graph",
            border_style="cyan",
        )
    )

    if stats["node_types"]:
        console.print(Rule("[dim]Node types[/dim]"))
        for ntype, count in sorted(
            stats["node_types"].items(), key=lambda x: x[1], reverse=True
        ):
            bar = "█" * min(count, 20)
            console.print(f"  [cyan]{ntype:<14}[/cyan] {bar} {count}")

    if stats["edge_types"]:
        console.print(Rule("[dim]Relationships[/dim]"))
        for etype, count in sorted(
            stats["edge_types"].items(), key=lambda x: x[1], reverse=True
        ):
            console.print(f"  [dim]{etype:<20}[/dim] {count}")


def _run_show(db_path: str) -> None:
    from nj.graph.repo import GraphRepo

    repo = GraphRepo(db_path)
    person_nodes = repo.get_nodes_by_type("person")
    if not person_nodes:
        console.print(
            "[yellow]Graph is empty.[/yellow] "
            "Run [bold]nj graph build[/bold] first."
        )
        return

    person = person_nodes[0]
    tree = Tree(
        f"[bold cyan]{person.label}[/bold cyan] [dim](you)[/dim]"
    )

    skill_neighbors = repo.get_neighbors(person.id, "HAS_SKILL")
    if skill_neighbors:
        skills_branch = tree.add(
            f"[green]Skills[/green] [dim]({len(skill_neighbors)})[/dim]"
        )
        for n in sorted(skill_neighbors, key=lambda x: x["weight"], reverse=True)[:10]:
            strength = "●" * min(int(n["weight"] * 3), 5)
            skills_branch.add(
                f"[green]{n['label']}[/green] [dim]{strength}[/dim]"
            )
        if len(skill_neighbors) > 10:
            skills_branch.add(
                f"[dim]... and {len(skill_neighbors) - 10} more[/dim]"
            )

    company_neighbors = repo.get_neighbors(person.id, "WORKED_AT")
    if company_neighbors:
        co_branch = tree.add(
            f"[yellow]Companies[/yellow] [dim]({len(company_neighbors)})[/dim]"
        )
        for n in company_neighbors:
            title = n.get("properties", {}).get("title", "")
            co_branch.add(
                f"[yellow]{n['label']}[/yellow] [dim]{title}[/dim]"
            )

    project_neighbors = repo.get_neighbors(person.id, "BUILT")
    if project_neighbors:
        proj_branch = tree.add(
            f"[magenta]Projects[/magenta] [dim]({len(project_neighbors)})[/dim]"
        )
        for n in project_neighbors:
            anchor = (
                " [cyan][anchor][/cyan]"
                if n.get("properties", {}).get("anchor")
                else ""
            )
            proj_branch.add(f"[magenta]{n['label']}[/magenta]{anchor}")

    role_neighbors = repo.get_neighbors(person.id, "APPLIED_TO")
    roles_only = [n for n in role_neighbors if n["node_type"] == "role"]
    if roles_only:
        role_branch = tree.add(
            f"[red]Applied roles[/red] [dim]({len(roles_only)})[/dim]"
        )
        for n in sorted(
            roles_only,
            key=lambda x: x.get("properties", {}).get("score", 0),
            reverse=True,
        )[:8]:
            score = n.get("properties", {}).get("score", 0)
            role_branch.add(
                f"[red]{n['label']}[/red] [dim]score: {score}[/dim]"
            )

    console.print(tree)


def _run_path(from_label: str, to_label: str, db_path: str) -> None:
    if not from_label or not to_label:
        console.print(
            "[red]Usage:[/red] graph path <from> <to>\n"
            "Example: graph path PyTorch 'Senior ML Engineer'"
        )
        return

    from nj.graph.repo import GraphRepo

    repo = GraphRepo(db_path)
    path = repo.find_path(from_label, to_label)

    if not path:
        console.print(
            f"[yellow]No path found from[/yellow] '{from_label}' → '{to_label}'\n"
            "[dim]Try broader terms or run nj graph build first.[/dim]"
        )
        return

    console.print(f"\n[bold]Path:[/bold] {from_label} → {to_label}\n")
    for i, node in enumerate(path):
        arrow = "→ " if i > 0 else "  "
        color = {
            "skill": "green",
            "role": "red",
            "company": "yellow",
            "project": "magenta",
            "technology": "cyan",
        }.get(node["type"], "white")
        console.print(
            f"  {arrow}[{color}]{node['label']}[/{color}] "
            f"[dim]({node['type']})[/dim]"
        )


def _run_skills(db_path: str) -> None:
    from nj.graph.repo import GraphRepo

    repo = GraphRepo(db_path)
    skills = repo.get_nodes_by_type("skill")

    if not skills:
        console.print(
            "[yellow]No skills in graph yet.[/yellow] "
            "Run [bold]nj graph build[/bold]."
        )
        return

    gap_skills = [s for s in skills if s.properties.get("is_gap")]
    your_skills = [s for s in skills if not s.properties.get("is_gap")]

    console.print(
        f"\n[bold]Your skills[/bold] ([green]{len(your_skills)}[/green] nodes)\n"
    )
    for s in sorted(your_skills, key=lambda x: x.label)[:20]:
        cat = s.properties.get("category", "")
        console.print(f"  [green]✓[/green] {s.label} [dim]{cat}[/dim]")

    if gap_skills:
        console.print(
            f"\n[bold]Gap skills[/bold] ([red]{len(gap_skills)}[/red] nodes)\n"
        )
        for s in sorted(gap_skills, key=lambda x: x.label)[:15]:
            console.print(f"  [red]✗[/red] {s.label}")


def _run_companies(db_path: str) -> None:
    from nj.graph.repo import GraphRepo

    repo = GraphRepo(db_path)
    companies = repo.get_nodes_by_type("company")

    if not companies:
        console.print("[yellow]No companies in graph yet.[/yellow]")
        return

    table = Table(title=f"Companies ({len(companies)})", box=box.SIMPLE)
    table.add_column("Company", width=35)
    table.add_column("Type", width=12)
    table.add_column("Source", width=12)

    for c in sorted(companies, key=lambda x: x.label):
        ctype = c.properties.get("status", "")
        table.add_row(c.label[:35], str(ctype or "")[:12], c.source[:12])

    console.print(table)


def _show_graph_help() -> None:
    console.print(
        Panel(
            "[bold]nj graph — Career Knowledge Graph[/bold]\n\n"
            "Commands:\n"
            "  [cyan]nj graph build[/cyan]               build from your CV + scores\n"
            "  [cyan]nj graph show[/cyan]                visualize your career tree\n"
            "  [cyan]nj graph stats[/cyan]               graph statistics\n"
            "  [cyan]nj graph skills[/cyan]              your skills + gaps\n"
            "  [cyan]nj graph companies[/cyan]           companies in your graph\n"
            "  [cyan]nj graph path PyTorch 'ML Engineer'[/cyan]  skill path\n\n"
            "[dim]The graph grows automatically as you use nj.[/dim]",
            border_style="cyan",
        )
    )
