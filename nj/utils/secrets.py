from __future__ import annotations

import os

from dotenv import load_dotenv

_loaded = False


def bootstrap() -> None:
    """Load .env once at process startup. Idempotent."""
    global _loaded
    if not _loaded:
        load_dotenv()
        _loaded = True


def get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# Status report used by `nj config --check-keys`
_KEYS: list[tuple[str, str, bool]] = [
    ("ANTHROPIC_API_KEY", "Claude AI — required if provider=claude", False),
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
    """Return status of every configured secret key."""
    results = []
    for key, description, required in _KEYS:
        value = os.getenv(key, "")
        results.append(
            {
                "key": key,
                "description": description,
                "required": required,
                "set": bool(value),
            }
        )
    return results
