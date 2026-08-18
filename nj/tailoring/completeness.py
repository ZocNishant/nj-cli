"""Reject a tailored CV that quietly lost content.

`anti_hallucination` is the guard against *addition*: it compares set membership
and flags anything in the draft that is absent from the base CV. Its docstring
is explicit that "reordering, dropping, or rewording an entry is allowed" —
which is correct for what it was built to do, and leaves the opposite failure
completely unguarded.

That gap shipped a real CV. A prompt bug showed the drafter only the first 28%
of the base CV, so it returned six of thirteen sections; the rendered PDF had
empty Projects, Certifications and Soft Skills headings and a single job. The
validator passed it, the reviewer approved it, the page budget was satisfied,
and every log line said success. Nothing in the pipeline was looking.

The rule is deliberately coarse: *entries* and *sections* must survive, their
*bullets* need not. Trimming an entry to two bullets is the tailoring the
prompt asks for; deleting the entry is not tailoring, it is loss. Findings here
are BLOCKING, and blocking is safe because the fallback — the suppressed base
CV — is by construction complete.
"""

from __future__ import annotations

from nj.utils.logger import get_logger

logger = get_logger(__name__)

# (top-level key, field naming one entry, human label). A section is checked
# only when the base CV actually has it, so a candidate with no certifications
# is never asked to keep certifications.
_ENTRY_RULES = [
    ("experience", "company", "experience entry"),
    ("projects", "name", "project"),
    ("education", "institution", "education entry"),
    ("certifications", "name", "certification"),
]


def _entry_key(entry: object, field: str) -> str:
    if isinstance(entry, dict):
        return str(entry.get(field, "")).strip().lower()
    return str(getattr(entry, field, "")).strip().lower()


def _present(value: object) -> bool:
    """Whether a section carries anything. [] and "" are as absent as None."""
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def validate_completeness(original: dict, tailored: dict) -> tuple[bool, list[str]]:
    """Reject a draft that dropped sections or entries. Returns (ok, violations).

    Only ever compares against what the base CV holds, so this cannot demand
    content the candidate does not have.
    """
    violations: list[str] = []

    for key, value in original.items():
        if not _present(value):
            continue
        if not _present(tailored.get(key)):
            violations.append(f"Dropped section: '{key}' is in your CV but missing from the draft")

    for key, field, label in _ENTRY_RULES:
        source = original.get(key)
        if not isinstance(source, list):
            continue
        drafted = tailored.get(key)
        drafted_keys = (
            {_entry_key(e, field) for e in drafted} if isinstance(drafted, list) else set()
        )
        for entry in source:
            name = _entry_key(entry, field)
            if name and name not in drafted_keys:
                shown = entry.get(field) if isinstance(entry, dict) else name
                violations.append(f"Dropped {label}: {shown!r} is in your CV but not the draft")

    is_complete = not violations
    if not is_complete:
        logger.warning(
            "completeness_violation",
            violation_count=len(violations),
            violations=violations[:3],
        )
    else:
        logger.debug("completeness_passed")
    return is_complete, violations
