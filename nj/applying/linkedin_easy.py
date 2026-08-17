"""LinkedIn Easy Apply automation — intentionally not implemented.

This module was a placeholder for driving Easy Apply through a browser session
authenticated with the operator's `li_at` cookie. It stays unimplemented on
purpose, for the same reason `nj.scrapers.linkedin` is stubbed: automating the
account the operator job-hunts from risks a checkpoint challenge or a permanent
ban, and submitting applications unattended is worse than scraping — a bad
submission is visible to the employer and cannot be taken back.

`nj` therefore stops at generating the tailored CV and cover letter. Submitting
is a human step. `ApplyConfig.automation_phase` exists for a future supervised
mode; nothing reads it to send anything today.
"""

from __future__ import annotations

from nj.utils.logger import get_logger

logger = get_logger(__name__)

DISABLED_REASON = (
    "LinkedIn Easy Apply automation is disabled: it would drive the operator's "
    "primary account and submit applications that cannot be retracted. Generate "
    "the CV and cover letter with `nj tailor`, then submit by hand."
)


class EasyApplyDisabledError(RuntimeError):
    """Raised when something tries to submit an application automatically."""


def apply_to_job(*args: object, **kwargs: object) -> None:
    """Refuse to auto-submit, loudly.

    Raising rather than returning a falsy result is deliberate: a caller that
    silently treats "nothing happened" as "applied" would mark jobs as submitted
    in the database that were never sent.
    """
    del args, kwargs
    logger.warning("linkedin_easy_apply_disabled", reason=DISABLED_REASON)
    raise EasyApplyDisabledError(DISABLED_REASON)
