from __future__ import annotations

import re
from collections import Counter

from nj.utils.logger import get_logger

logger = get_logger(__name__)

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "our",
    "your",
    "their",
    "its",
    "this",
    "that",
    "these",
    "those",
    "we",
    "you",
    "they",
    "it",
    "he",
    "she",
    "who",
    "which",
    "what",
    "not",
    "no",
    "nor",
    "so",
    "yet",
    "both",
    "either",
    "neither",
    "as",
    "if",
    "than",
    "then",
    "when",
    "where",
    "while",
    "although",
    "must",
    "also",
    "well",
    "such",
    "more",
    "other",
    "into",
    "through",
    "experience",
    "work",
    "team",
    "strong",
    "ability",
    "skills",
    "role",
    "position",
    "candidate",
    "join",
    "looking",
    "seeking",
    "years",
}


def extract_keywords(
    jd_text: str,
    existing_skills: list[str],
    top_n: int = 15,
) -> list[str]:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.-]{2,}\b", jd_text)
    tokens = [t.lower() for t in tokens if t.lower() not in STOPWORDS]
    freq = Counter(tokens)
    existing_lower = {s.lower() for s in existing_skills}
    ranked = [
        word
        for word, _ in freq.most_common(60)
        if word not in existing_lower and len(word) > 3
    ]
    logger.debug(
        "keywords_extracted", count=len(ranked[:top_n]), keywords=ranked[:top_n]
    )
    return ranked[:top_n]


def flatten_skills(skills: dict) -> list[str]:
    flat = []
    for items in skills.values():
        if isinstance(items, list):
            flat.extend(items)
    return flat
