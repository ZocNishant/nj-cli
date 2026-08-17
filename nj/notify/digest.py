from __future__ import annotations

from datetime import UTC, datetime


def format_summary_table(applications: list[dict]) -> str:
    if not applications:
        return "No applications in this run."

    lines = [
        f"nj daily summary — {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"Total applications: {len(applications)}",
        "",
        f"{'Score':<7} {'Status':<12} {'Company':<22} {'Role':<30} {'Visa':<12}",
        "-" * 85,
    ]
    for app in sorted(applications, key=lambda a: a.get("score", 0), reverse=True):
        score = str(app.get("score", 0))
        status = app.get("status", "")[:12]
        company = app.get("company", "")[:22]
        title = app.get("title", "")[:30]
        visa = app.get("visa_label", "")[:12]
        lines.append(f"{score:<7} {status:<12} {company:<22} {title:<30} {visa:<12}")

    avg = sum(a.get("score", 0) for a in applications) / len(applications) if applications else 0
    lines += ["", f"Average score: {avg:.1f}"]
    return "\n".join(lines)
