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


def validate_tailored_cv(
    original: dict,
    tailored: dict,
) -> tuple[bool, list[str]]:
    violations = []

    tailored_text = str(tailored)
    original_text = str(original)

    for pattern in HIGH_RISK_PATTERNS:
        original_matches = set(re.findall(pattern, original_text, re.IGNORECASE))
        tailored_matches = set(re.findall(pattern, tailored_text, re.IGNORECASE))
        new_matches = tailored_matches - original_matches
        for match in new_matches:
            violations.append(
                f"Invented content detected: '{match}' not in original CV"
            )

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
