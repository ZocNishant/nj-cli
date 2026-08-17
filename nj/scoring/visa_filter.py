from __future__ import annotations

import re

from nj.models.config import VisaConfig
from nj.models.job import Job, VisaLabel
from nj.utils.logger import get_logger

logger = get_logger(__name__)


# Ordered, negation-aware sponsorship classification.
#
# The previous implementation did bare substring matching, which failed in both
# directions on real postings:
#   "We sponsor H-1B. Must be authorized to work in the US at time of hire."
#       -> BLOCKED, because "must be authorized" was an exclude keyword.
#   "We do not sponsor employment visas."
#       -> CONFIRMED, because "sponsor" was an include keyword.
#
# Both are expensive for an OPT candidate: the first silently drops jobs that
# would have sponsored, the second burns API credit and applications on jobs
# that never will. The patterns below match the phrase around the verb rather
# than the keyword alone, and BLOCK is evaluated before SPONSOR so a negated
# mention of sponsorship can never read as an offer of one.
#
# "Must be authorized to work in the US" is deliberately NOT a block: someone on
# OPT is authorized to work. The disqualifier is a requirement to be authorized
# without sponsorship, now or in the future.

_BLOCK_PHRASES = [
    # negated sponsorship verbs
    r"\b(?:do(?:es)?\s+not|will\s+not|won'?t|cannot|can'?t|are\s+not\s+able\s+to|"
    r"is\s+not\s+able\s+to|unable\s+to|not\s+in\s+a\s+position\s+to)\s+"
    r"(?:currently\s+|presently\s+|be\s+able\s+to\s+)?"
    r"(?:offer|provide|support|consider|apply\s+for)?\s*"
    r"(?:visa\s+|employment\s+|immigration\s+)?sponsor",
    # negated sponsorship nouns
    r"\bno\s+(?:visa\s+|employment\s+|immigration\s+)?sponsorship\b",
    r"\bsponsorship\s+is\s+not\s+(?:available|offered|provided|possible)\b",
    r"\bwithout\s+(?:the\s+need\s+for\s+)?(?:visa\s+|employment\s+)?sponsorship\b",
    r"\b(?:does\s+)?not\s+require\s+(?:visa\s+|employment\s+)?sponsorship\b",
    r"\bnot\s+now\s+or\s+in\s+the\s+future\b",
    # citizenship / status gates
    r"\b(?:u\.?s\.?\s+)?citizens?(?:hip)?\s+(?:is\s+)?(?:required|only)\b",
    r"\bmust\s+be\s+(?:a\s+)?u\.?s\.?\s+citizen\b",
    r"\bcitizens?\s+or\s+permanent\s+residents?\s+only\b",
    r"\bgreen\s+card\s+(?:holders?\s+)?only\b",
    r"\bu\.?s\.?\s+persons?\s+only\b",
    # clearance work is effectively citizen-only
    r"\b(?:active\s+|current\s+)?security\s+clearance\b",
    r"\b(?:ts\/sci|top\s+secret)\b",
]

_SPONSOR_PHRASES = [
    r"\b(?:will|do|does|can|happy\s+to|willing\s+to|able\s+to|open\s+to|glad\s+to)\s+"
    r"sponsor\b",
    r"\bwe\s+sponsor\b",
    r"\bsponsorship\s+(?:is\s+)?(?:available|offered|provided|possible|supported)\b",
    r"\b(?:visa|employment|immigration)\s+sponsorship\b",
    r"\bsponsor(?:ship)?\s+for\s+qualified\b",
    r"\bvisa\s+support\b",
    r"\bimmigration\s+support\b",
    r"\bsponsor\s+(?:work\s+)?visas?\b",
]

# Acronyms are matched case-sensitively against the original text so that
# "opt-in", "opt out" and "options" do not read as Optional Practical Training.
_SPONSOR_ACRONYMS = [
    r"\bSTEM\s+OPT\b",
    r"\bOPT\b(?!\s*[-–]?\s*(?:in|out|ing))",
    r"\bCPT\b",
    r"\bH-?1-?B\b",
    r"\bF-?1\b",
    r"\bEAD\b",
]

_LIKELY_PHRASES = [
    r"\binternational\s+(?:candidates?|applicants?|students?|hires?)\b",
    r"\bglobal\s+candidates?\b",
    r"\bworldwide\b",
    r"\bopen\s+to\s+candidates?\s+(?:from\s+)?(?:anywhere|worldwide)\b",
    r"\brelocation\s+(?:and|&)\s+immigration\b",
]

_BLOCK_RE = [re.compile(p, re.I) for p in _BLOCK_PHRASES]
_SPONSOR_RE = [re.compile(p, re.I) for p in _SPONSOR_PHRASES]
_ACRONYM_RE = [re.compile(p) for p in _SPONSOR_ACRONYMS]
_LIKELY_RE = [re.compile(p, re.I) for p in _LIKELY_PHRASES]


class VisaFilter:
    def __init__(self, config: VisaConfig):
        self.config = config

    def classify(self, description: str) -> VisaLabel:
        label, _ = self.explain(description)
        return label

    def explain(self, description: str) -> tuple[VisaLabel, str]:
        """Classify sponsorship posture and return the evidence that decided it.

        Returning the matched phrase lets `nj search` and `nj explain` show why a
        job was dropped, which is the only practical way to catch a
        misclassification before it costs an application.
        """
        if not self.config.enabled:
            return VisaLabel.UNKNOWN, "visa filtering disabled"

        text = description or ""
        lowered = text.lower()

        # User-supplied overrides win outright, in both directions. These are
        # exact substrings from config.yaml, so they stay literal on purpose.
        for kw in self.config.exclude_keywords:
            if kw and kw.lower() in lowered:
                return VisaLabel.BLOCKED, f"config exclude keyword: {kw!r}"

        for rx in _BLOCK_RE:
            m = rx.search(text)
            if m:
                return VisaLabel.BLOCKED, f"no-sponsorship language: {m.group().strip()!r}"

        for kw in self.config.include_keywords:
            if kw and kw.lower() in lowered:
                return VisaLabel.CONFIRMED, f"config include keyword: {kw!r}"

        for rx in _SPONSOR_RE:
            m = rx.search(text)
            if m:
                return VisaLabel.CONFIRMED, f"sponsorship offered: {m.group().strip()!r}"

        for rx in _ACRONYM_RE:
            m = rx.search(text)
            if m:
                return VisaLabel.CONFIRMED, f"visa acronym present: {m.group().strip()!r}"

        for rx in _LIKELY_RE:
            m = rx.search(text)
            if m:
                return (
                    VisaLabel.LIKELY,
                    f"international-friendly language: {m.group().strip()!r}",
                )

        return VisaLabel.UNKNOWN, "no sponsorship signal found"

    def should_skip(self, job: Job) -> bool:
        if not self.config.enabled:
            return False
        if not self.config.skip_no_sponsorship:
            return False
        skip = job.visa_label == VisaLabel.BLOCKED
        if skip:
            logger.info(
                "visa_blocked",
                job_id=job.id,
                company=job.company,
                title=job.title,
            )
        return skip
