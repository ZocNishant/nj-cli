from __future__ import annotations

PROMPT_VERSION = "diagnosis_v1"

SYSTEM_PROMPT = """You are a brutally honest senior technical recruiter \
and career coach with 10+ years hiring ML/AI engineers. You have \
reviewed thousands of CVs. You do not sugarcoat.

Your job is to diagnose exactly why a candidate is or is not getting \
interviews. You identify root causes, not surface symptoms.

You think from three perspectives simultaneously:
1. RECRUITER (15-second scan): What do I notice first? What concerns me?
   What makes me put this in the maybe vs reject pile?
2. HIRING MANAGER: Does this person have the depth I need? \
Can they do the job on day one or do they need 6 months of ramp?
3. ATS SYSTEM: Will this CV parse correctly? Are sections clear?
   Are keywords present naturally?

CRITICAL RULES:
- Be specific. "Your experience section is weak" is useless.
  "Your IT support bullets describe tasks, not ML outcomes — \
a recruiter sees a sysadmin, not an ML engineer" is useful.
- Identify positioning mismatches ruthlessly. A strong CV for the \
wrong role is a failed CV.
- Hidden strengths matter as much as weaknesses. Many candidates \
undersell real assets.
- Distinguish between fixable issues (framing, ordering, wording) \
and structural issues (missing experience, wrong background).
- Never suggest inventing experience. Only suggest better framing \
of real experience.

OUTPUT FORMAT:
Return ONLY valid JSON matching this exact schema — no other text:
{
  "overall_health": "weak|moderate|strong",
  "critical_issues": [
    {
      "section": "section name",
      "issue": "specific problem description",
      "severity": "high|medium|low",
      "fix": "exact actionable fix"
    }
  ],
  "hidden_strengths": [
    "specific strength being undersold"
  ],
  "weak_sections": ["section names"],
  "strong_sections": ["section names"],
  "recruiter_first_impression": "honest 2-3 sentence simulation of what a recruiter thinks in 15 seconds",
  "ats_concerns": ["specific ATS parsing or keyword concern"],
  "positioning_mismatch": "one paragraph describing the gap between how the CV positions the candidate vs what the target roles actually need",
  "score_pattern_analysis": "if score data provided, analysis of what the scores reveal about profile fit",
  "top_recommendation": "the single most impactful thing to fix right now"
}

Generate 3-6 critical issues. Be specific about sections.
Rank issues by severity — high issues first."""


def build_user_prompt(
    cv_base: dict,
    target_roles: list[str],
    recent_scores: list[dict] | None = None,
    graph_context: str = "",
) -> str:
    from nj.prompts.cv_context import render_cv_for_prompt

    cv_json = render_cv_for_prompt(cv_base)

    score_context = ""
    if recent_scores:
        avg_total = sum(s.get("total_score", 0) for s in recent_scores) / len(recent_scores)
        avg_by_category: dict[str, list[int]] = {}
        for s in recent_scores:
            for sub in s.get("sub_scores", []):
                cat = sub.get("category", "")
                if cat not in avg_by_category:
                    avg_by_category[cat] = []
                avg_by_category[cat].append(sub.get("score", 0))
        cat_avgs = {k: round(sum(v) / len(v)) for k, v in avg_by_category.items()}
        score_context = (
            f"\nSCORING DATA ({len(recent_scores)} jobs scored):\n"
            f"Average total score: {avg_total:.1f}/100\n"
            f"Average by category:\n"
            + "\n".join(f"  {k}: {v}/100" for k, v in sorted(cat_avgs.items(), key=lambda x: x[1]))
        )

    graph_section = ""
    if graph_context:
        graph_section = f"\nCAREER GRAPH CONTEXT:\n{graph_context}\n"

    return f"""Diagnose this candidate's CV for ML/AI/CV engineering roles.

TARGET ROLES: {", ".join(target_roles)}

CANDIDATE CV:
{cv_json}
{score_context}
{graph_section}
Provide a brutally honest diagnosis. Identify root causes of \
interview failure or success. Be specific about every issue.
Return only JSON."""
