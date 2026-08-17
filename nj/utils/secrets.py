"""Typed credential loading.

All secrets come from the environment (or `.env`), never from `config.yaml`.
`Settings` is the single source of truth; `get()` and `check_all()` remain as
thin wrappers so existing call sites keep working.

Secrets are held as `SecretStr`, so a stray f-string or log line renders
`**********` instead of the key. Call `.get_secret_value()` at the point of use.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM providers
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    groq_api_key: SecretStr = Field(default=SecretStr(""))
    freellmapi_api_key: SecretStr = Field(default=SecretStr(""))
    openai_api_key: SecretStr = Field(default=SecretStr(""))

    # Job sources
    jsearch_api_key: SecretStr = Field(default=SecretStr(""))
    adzuna_app_id: SecretStr = Field(default=SecretStr(""))
    adzuna_app_key: SecretStr = Field(default=SecretStr(""))
    usajobs_api_key: SecretStr = Field(default=SecretStr(""))
    usajobs_user_agent: str = ""
    linkedin_li_at: SecretStr = Field(default=SecretStr(""))

    # Notifications
    sendgrid_api_key: SecretStr = Field(default=SecretStr(""))
    gmail_credentials_json: str = ""

    def value(self, key: str) -> str:
        """Return a setting by env-var name, unwrapping SecretStr."""
        raw = getattr(self, key.lower(), "")
        return raw.get_secret_value() if isinstance(raw, SecretStr) else str(raw)

    def is_set(self, key: str) -> bool:
        return bool(self.value(key))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def bootstrap() -> None:
    """Load credentials once at process startup. Idempotent.

    Kept for the CLI entry point. `Settings` reads `.env` itself, so this only
    warms the cache — but it also keeps `os.getenv` call sites working, since
    pydantic-settings does not write back into the process environment.
    """
    settings = get_settings()
    for field in Settings.model_fields:
        env_name = field.upper()
        if not os.getenv(env_name):
            value = settings.value(env_name)
            if value:
                os.environ[env_name] = value


def get(key: str, default: str = "") -> str:
    return get_settings().value(key) or os.getenv(key, default)


# Status report used by `nj config --check-keys`
_KEYS: list[tuple[str, str, bool]] = [
    ("ANTHROPIC_API_KEY", "Claude AI — required if provider=claude", True),
    ("GROQ_API_KEY", "Groq — required if provider=freellmapi", False),
    ("JSEARCH_API_KEY", "JSearch / RapidAPI (job aggregator)", False),
    ("LINKEDIN_LI_AT", "LinkedIn session cookie (scraper)", False),
    ("ADZUNA_APP_ID", "Adzuna App ID (job search)", False),
    ("ADZUNA_APP_KEY", "Adzuna App Key (job search)", False),
    ("USAJOBS_API_KEY", "USAJobs.gov (government roles)", False),
    ("USAJOBS_USER_AGENT", "USAJobs user-agent email", False),
    ("SENDGRID_API_KEY", "SendGrid (email notifications)", False),
    ("GMAIL_CREDENTIALS_JSON", "Gmail OAuth2 credentials path", False),
]


def check_all() -> list[dict]:
    """Return status of every configured secret key. Never returns values."""
    settings = get_settings()
    return [
        {
            "key": key,
            "description": description,
            "required": required,
            "set": settings.is_set(key) or bool(os.getenv(key, "")),
        }
        for key, description, required in _KEYS
    ]
