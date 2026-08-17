"""Schemas for the adversarial review pass over a tailored draft.

The drafter writes; the reviewer tries to prove the draft wrong. Findings come
from two places that are deliberately not treated alike:

* `Source.VALIDATOR` — `nj.tailoring.anti_hallucination.validate_tailored_cv`.
  Set membership against the base CV. It cannot be argued with and it cannot be
  talked out of a finding by anything in the draft, so its findings block.
* `Source.REVIEWER` — the Haiku reviewer. It catches what set comparison cannot:
  a date quietly widened, a contribution upgraded from "contributed to" to
  "led", a skill implied by phrasing rather than named. It is a language model
  reading model output, so it can be wrong in both directions; its findings are
  advisory and drive a revision round rather than a hard rejection.

`approved` is therefore not "the reviewer was happy" — it is "nothing blocking
survived", which only the validator can decide.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"


class Source(str, Enum):
    VALIDATOR = "validator"
    REVIEWER = "reviewer"


class Revision(BaseModel):
    """One thing the draft asserts that the base CV does not support."""

    location: str = Field(
        default="", description="Where in the draft, e.g. experience[0].bullets[2]"
    )
    claim: str = Field(description="The offending text, quoted from the draft")
    problem: str = Field(description="Why the base CV does not support it")
    severity: Severity = Severity.ADVISORY
    source: Source = Source.REVIEWER

    def as_instruction(self) -> str:
        """Render as a line the drafter can act on in a revision round."""
        where = f" ({self.location})" if self.location else ""
        return f"- {self.claim!r}{where}: {self.problem}"


class ReviewReport(BaseModel):
    """The verdict on one draft."""

    revisions: list[Revision] = []
    summary: str = ""
    # Set to False when the reviewer call itself failed. The draft is then
    # governed by the validator alone; callers should not read a degraded
    # review as a clean one.
    reviewer_ran: bool = True

    @property
    def blocking(self) -> list[Revision]:
        return [r for r in self.revisions if r.severity == Severity.BLOCKING]

    @property
    def advisory(self) -> list[Revision]:
        return [r for r in self.revisions if r.severity == Severity.ADVISORY]

    @property
    def approved(self) -> bool:
        """True only when nothing blocking survived."""
        return not self.blocking

    @property
    def clean(self) -> bool:
        """True when neither layer found anything at all."""
        return not self.revisions

    def feedback_block(self, limit: int = 12) -> str:
        """The revision list, formatted for the drafter's next attempt.

        Blocking findings come first: if the list is truncated, the ones that
        actually gate the output are the ones that survive.
        """
        ordered = self.blocking + self.advisory
        if not ordered:
            return ""
        lines = [r.as_instruction() for r in ordered[:limit]]
        return "\n".join(lines)


# Constrained decoding schema for the reviewer call. The reviewer only ever
# proposes findings — `severity` is absent on purpose, because whether a finding
# blocks is the validator's call, not the model's.
REVIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "revisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "claim": {"type": "string"},
                    "problem": {"type": "string"},
                },
                "required": ["location", "claim", "problem"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["revisions", "summary"],
    "additionalProperties": False,
}
