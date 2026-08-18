"""Serialising the base CV into a prompt.

The base CV is the candidate's trusted, operator-authored record, and it is the
only thing standing between the drafter and an invented claim. Every prompt that
carries it used to slice it with a bare `[:3000]`, which is how a real CV lost
its projects: at 10,874 characters the tailoring prompt showed the model 28% of
it, cut mid-token inside the first job. The model then returned exactly the six
top-level sections it could see, and nothing downstream objected — the
anti-hallucination validator only rejects content that was *added*, so a draft
missing every project is, to it, a clean draft.

So: never truncate silently. A CV large enough to be a real cost is a fact the
operator needs told, not a slice taken behind their back.
"""

from __future__ import annotations

import json

from nj.utils.logger import get_logger

logger = get_logger(__name__)

# Roughly 15k tokens of CV. Far above any real one — a 4-page CV serialises to
# about 12k characters — so crossing it means something is wrong with the file
# rather than the candidate being unusually accomplished.
CV_CONTEXT_WARN_CHARS = 60_000


def render_cv_for_prompt(cv_base: dict) -> str:
    """The CV as JSON for a prompt, whole.

    Returns every byte. The size check logs and never trims: a caller that
    silently dropped the tail would reintroduce the exact bug this module
    exists to prevent.
    """
    rendered = json.dumps(cv_base, indent=2)
    if len(rendered) > CV_CONTEXT_WARN_CHARS:
        logger.warning(
            "cv_context_unusually_large",
            chars=len(rendered),
            threshold=CV_CONTEXT_WARN_CHARS,
            sections=sorted(cv_base.keys()),
        )
    return rendered
