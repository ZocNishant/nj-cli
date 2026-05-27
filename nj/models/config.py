from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from nj.models.score import DEFAULT_WEIGHTS


class LLMConfig(BaseModel):
    provider: str = "claude"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    freellmapi_base_url: str = "http://localhost:3001/v1"
    freellmapi_api_key: str = "freellmapi-your-key-here"
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
    include_keywords: list[str] = ["OPT", "CPT", "H1B", "visa sponsorship", "sponsor"]
    exclude_keywords: list[str] = [
        "no sponsorship",
        "citizen only",
        "green card only",
        "must be authorized",
        "no visa",
    ]


class ScoringConfig(BaseModel):
    threshold: int = 62
    calibration_sample: int = 30
    weights: dict[str, float] = {k.value: v for k, v in DEFAULT_WEIGHTS.items()}


class ApplyConfig(BaseModel):
    enabled: bool = False
    max_per_day: int = 5
    delay_min: int = 30
    delay_max: int = 90
    automation_phase: int = 1


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
    def load(cls, path: str = "config.yaml") -> "Config":
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
