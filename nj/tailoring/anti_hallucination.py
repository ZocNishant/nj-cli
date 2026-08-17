from __future__ import annotations

import re

from nj.utils.logger import get_logger

logger = get_logger(__name__)


def extract_entities(cv: dict) -> set[str]:
    entities: set[str] = set()

    def add_text(text: str) -> None:
        if not text or not isinstance(text, str):
            return
        words = re.findall(r"\b[A-Z][a-zA-Z0-9+#.-]{1,}\b", text)
        entities.update(words)
        numbers = re.findall(r"\b\d+(?:\.\d+)?%?", text)
        entities.update(numbers)

    def walk(obj: object) -> None:
        if isinstance(obj, str):
            add_text(obj)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)

    walk(cv)
    return entities


ALLOWED_NEW_ENTITIES = {
    "the",
    "and",
    "for",
    "with",
    "using",
    "via",
    "at",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "Present",
    "Expected",
    "Incoming",
}

HIGH_RISK_PATTERNS = [
    r"\b(Google|Microsoft|Meta|Amazon|Apple|OpenAI|DeepMind|NVIDIA)\b",
    r"\b\d{4}\b",
    r"\b\d+(?:\.\d+)?%",
    r"\b(PhD|published|patent|award|prize)\b",
]


def _normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9+#.]+", "", str(value).lower())


def _collect(cv: dict, section: str, field: str) -> dict[str, str]:
    """Map normalized -> original for `field` across every entry in `cv[section]`.

    Comparison happens on the normalized key so casing and punctuation do not
    register as inventions; the original spelling is kept for the message.
    """
    out: dict[str, str] = {}
    for entry in cv.get(section, []) or []:
        if isinstance(entry, dict):
            value = entry.get(field)
            if value:
                out.setdefault(_normalize(value), str(value))
    return out


def _collect_skills(cv: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    skills = cv.get("skills", {}) or {}
    if isinstance(skills, dict):
        groups = [i for items in skills.values() if isinstance(items, list) for i in items]
    elif isinstance(skills, list):
        groups = list(skills)
    else:
        groups = []
    for item in groups:
        if item:
            out.setdefault(_normalize(item), str(item))
    return out


# Each rule names the claim it protects, so a violation message says what the
# model tried to invent rather than just which regex fired.
_STRUCTURAL_RULES = [
    ("employer", lambda cv: _collect(cv, "experience", "company")),
    ("job title", lambda cv: _collect(cv, "experience", "title")),
    ("institution", lambda cv: _collect(cv, "education", "institution")),
    ("degree", lambda cv: _collect(cv, "education", "degree")),
    ("project", lambda cv: _collect(cv, "projects", "name")),
    ("certification", lambda cv: _collect(cv, "certifications", "name")),
    ("skill", _collect_skills),
]


def validate_tailored_cv(
    original: dict,
    tailored: dict,
) -> tuple[bool, list[str]]:
    """Reject a tailored CV that asserts anything the source CV does not.

    Two layers. The structural pass compares the sets that carry factual
    claims — employers, titles, institutions, degrees, projects,
    certifications, skills — and flags any value present in the tailored CV but
    absent from the original. The regex pass catches free-text inventions
    inside bullets that no structural field would cover: years, percentages,
    named big-tech employers, and credential words.

    The structural pass is what makes the README's claim literally true. It
    only ever compares set membership, so reordering, dropping, or rewording an
    entry is allowed; adding a new one is not.
    """
    violations = []

    for label, collect in _STRUCTURAL_RULES:
        original_values = collect(original)
        tailored_values = collect(tailored)
        for key, shown in tailored_values.items():
            if key and key not in original_values:
                violations.append(f"Invented {label}: {shown!r} does not appear in your CV")

    tailored_text = str(tailored)
    original_text = str(original)

    for pattern in HIGH_RISK_PATTERNS:
        original_matches = set(re.findall(pattern, original_text, re.IGNORECASE))
        tailored_matches = set(re.findall(pattern, tailored_text, re.IGNORECASE))
        new_matches = tailored_matches - original_matches
        for match in new_matches:
            violations.append(f"Invented content detected: '{match}' not in original CV")

    is_valid = len(violations) == 0
    if not is_valid:
        logger.warning(
            "hallucination_detected",
            violation_count=len(violations),
            violations=violations[:3],
        )
    else:
        logger.debug("anti_hallucination_passed")

    return is_valid, violations
