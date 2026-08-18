from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

from nj.models.score import DEFAULT_WEIGHTS


class LLMConfig(BaseModel):
    """LLM routing.

    Work is tiered by how much the output quality matters. Bulk job scoring runs
    on the cheap model because it only has to rank; anything that ends up in
    front of a recruiter runs on a stronger one.
    """

    provider: str = "claude"
    # Default/fallback model when a task-specific tier is not set.
    model: str = "claude-sonnet-5"
    # Bulk scoring: dozens to hundreds of calls per run, output is a ranking.
    scoring_model: str = "claude-haiku-4-5"
    # CV tailoring and cover letters: this is what a human actually reads.
    tailoring_model: str = "claude-sonnet-5"
    # Adversarial review of a tailored draft. One or two calls per application,
    # and the task is narrow — find claims the base CV does not support — so the
    # cheap tier is the right one. It advises; it never gets a veto.
    review_model: str = "claude-haiku-4-5"
    # Diagnosis, interview prep, project framing: a few calls, highest stakes.
    reasoning_model: str = "claude-opus-5"
    api_key: str = ""
    freellmapi_base_url: str = "http://localhost:3001/v1"
    freellmapi_api_key: str = ""
    # Fallback for the OpenAI-compatible gateway path when no tier is set.
    # The four fields above are read for this provider too — see
    # nj/providers/registry.py. They used to be ignored here, which collapsed
    # every tier onto this one model and, worse, made the reviewer the same
    # model as the drafter. A model asked to audit its own output is the one
    # thing the drafter-reviewer split exists to prevent.
    freellmapi_model: str = "auto"


class SearchConfig(BaseModel):
    roles: list[str] = ["ML Engineer", "Computer Vision Engineer", "AI Engineer"]
    primary_region: str = "USA"
    include_global: bool = False
    keywords_exclude: list[str] = ["10+ years", "Staff Engineer", "Principal Engineer"]


class VisaConfig(BaseModel):
    enabled: bool = True
    status: str = "OPT"
    h1b_future: bool = True
    skip_no_sponsorship: bool = True
    # Both lists are literal-substring overrides layered on top of the
    # negation-aware patterns in nj/scoring/visa_filter.py. Leave them empty
    # unless you hit a posting the classifier gets wrong — a loose keyword here
    # silently overrides the phrase matching for every job.
    #
    # "must be authorized" used to live in exclude_keywords and was dropping
    # sponsoring employers wholesale: nearly every US posting says it, and it is
    # satisfied by OPT. "sponsor" used to live in include_keywords and matched
    # "we do not sponsor". Both are now handled by phrase patterns instead.
    include_keywords: list[str] = []
    exclude_keywords: list[str] = []


class ScoringConfig(BaseModel):
    threshold: int = 62
    calibration_sample: int = 30
    weights: dict[str, float] = {k.value: v for k, v in DEFAULT_WEIGHTS.items()}


def _coerce_phase(phase: object) -> bool:
    """`automation_phase: 1` meant "queue only"; anything higher meant tailor."""
    try:
        return int(phase) > 1
    except (TypeError, ValueError):
        return False


class ApplyConfig(BaseModel):
    enabled: bool = False
    max_per_day: int = 5
    delay_min: int = 30
    delay_max: int = 90
    # Whether `nj run` tailors the jobs it scores, or stops after queueing them
    # for `nj review`.
    #
    # This was an integer named `automation_phase`, read at exactly one place,
    # and at its default of 1 the command could never produce a CV — which made
    # the four stages after it unreachable, with nothing in the name to hint at
    # that. "Phase" also implied a progression toward auto-submission that the
    # project has deliberately abandoned: nj cannot submit, and
    # nj/applying/linkedin_easy.py raises rather than try.
    #
    # Unattended tailoring is safe under that same rule — nothing is sent
    # either way — so the flag says what it does and the default stays
    # conservative. `nj run --tailor` turns it on for a single run.
    tailor_unattended: bool = False

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_automation_phase(cls, data: object) -> object:
        """Read an existing config.yaml that still says `automation_phase`.

        Dropping the key outright would silently flip behaviour for anyone
        whose file sets it to 2 — they asked for unattended tailoring and would
        quietly stop getting it.
        """
        if isinstance(data, dict) and "automation_phase" in data:
            phase = data.pop("automation_phase")
            data.setdefault("tailor_unattended", _coerce_phase(phase))
        return data


class NotifyConfig(BaseModel):
    email_to: str = ""
    provider: str = "smtp"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sendgrid_api_key: str = ""


class ScheduleConfig(BaseModel):
    enabled: bool = True
    every_days: int = 3
    time: str = "08:00"


class ScraperConfig(BaseModel):
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "us"
    adzuna_enabled: bool = True
    remoteok_enabled: bool = True
    linkedin_enabled: bool = True
    jsearch_enabled: bool = True
    arbeitnow_enabled: bool = True
    weworkremotely_enabled: bool = True
    usajobs_enabled: bool = False


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    search: SearchConfig = SearchConfig()
    visa: VisaConfig = VisaConfig()
    scoring: ScoringConfig = ScoringConfig()
    apply: ApplyConfig = ApplyConfig()
    notify: NotifyConfig = NotifyConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    scraper: ScraperConfig = ScraperConfig()

    @classmethod
    def load(cls, path: str = "config.yaml") -> Config:
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
