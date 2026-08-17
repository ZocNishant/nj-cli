"""Credential loading via pydantic-settings.

The behaviour that matters here is not "can it read a value" but "does a
credential stay out of anything that gets printed" — this repo has leaked a key
to a public remote before.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from nj.utils import secrets as secrets_mod
from nj.utils.secrets import Settings, check_all, get, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """get_settings is lru_cached; tests must not see each other's env."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_secrets_do_not_appear_in_repr_or_str():
    s = Settings(anthropic_api_key=SecretStr("sk-ant-supersecret"))
    assert "supersecret" not in repr(s)
    assert "supersecret" not in str(s)
    assert "supersecret" not in repr(s.anthropic_api_key)


def test_secrets_do_not_leak_through_model_dump():
    """A structured log that dumps settings must not carry the key."""
    s = Settings(groq_api_key=SecretStr("gsk_supersecret"))
    assert "supersecret" not in str(s.model_dump())


def test_value_unwraps_the_secret_for_use():
    s = Settings(anthropic_api_key=SecretStr("sk-ant-abc123"))
    assert s.value("ANTHROPIC_API_KEY") == "sk-ant-abc123"
    assert s.value("anthropic_api_key") == "sk-ant-abc123"


def test_value_returns_empty_for_unset_and_unknown_keys():
    s = Settings()
    assert s.value("ANTHROPIC_API_KEY") == ""
    assert s.value("NOT_A_REAL_KEY") == ""


def test_is_set_reflects_presence():
    assert Settings(anthropic_api_key=SecretStr("x")).is_set("ANTHROPIC_API_KEY")
    assert not Settings().is_set("ANTHROPIC_API_KEY")


def test_plain_string_fields_are_not_wrapped():
    """usajobs_user_agent is an email, not a credential."""
    s = Settings(usajobs_user_agent="me@example.com")
    assert s.value("USAJOBS_USER_AGENT") == "me@example.com"


def test_settings_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
    get_settings.cache_clear()
    assert get_settings().value("ANTHROPIC_API_KEY") == "sk-ant-from-env"


def test_get_falls_back_to_os_environ(monkeypatch):
    """Callers still using get() for a key Settings does not model."""
    monkeypatch.setenv("SOME_OTHER_KEY", "value")
    assert get("SOME_OTHER_KEY") == "value"
    assert get("STILL_MISSING", "fallback") == "fallback"


def test_check_all_reports_status_without_exposing_values(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-supersecret")
    get_settings.cache_clear()

    report = check_all()
    keys = {r["key"] for r in report}
    assert "ANTHROPIC_API_KEY" in keys
    assert "LINKEDIN_LI_AT" in keys

    # No entry may carry the value itself.
    assert "supersecret" not in str(report)
    anthropic = next(r for r in report if r["key"] == "ANTHROPIC_API_KEY")
    assert anthropic["set"] is True
    assert anthropic["required"] is True


def test_check_all_marks_unset_keys(monkeypatch):
    monkeypatch.delenv("JSEARCH_API_KEY", raising=False)
    get_settings.cache_clear()
    entry = next(r for r in check_all() if r["key"] == "JSEARCH_API_KEY")
    assert entry["set"] is False


def test_bootstrap_is_idempotent(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_value")
    get_settings.cache_clear()
    secrets_mod.bootstrap()
    secrets_mod.bootstrap()
    assert get("GROQ_API_KEY") == "gsk_value"


def test_unknown_env_vars_are_ignored():
    """extra='ignore' — an unrelated var in .env must not blow up startup."""
    Settings(SOME_UNRELATED_VAR="x")  # must not raise
