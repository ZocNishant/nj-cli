from __future__ import annotations

import pytest

from nj.models.config import VisaConfig
from nj.scrapers.linkedin import ENABLE_ENV_VAR, LinkedInScraper, is_enabled
from nj.utils.rate_limiter import RateLimiter


def make_scraper() -> LinkedInScraper:
    return LinkedInScraper(
        session_cookie="fake-cookie",
        visa_config=VisaConfig(),
        headless=True,
    )


def test_linkedin_scraper_name() -> None:
    assert make_scraper().name() == "linkedin"


def test_linkedin_scrape_returns_nothing() -> None:
    """The scraper is stubbed; it must stay inert, not merely fail politely."""
    assert make_scraper().fetch(["ML Engineer"], "United States") == []


def test_linkedin_scrape_stays_inert_even_when_opted_in(monkeypatch) -> None:
    """The opt-in var gates a future implementation; it does not resurrect one."""
    monkeypatch.setenv(ENABLE_ENV_VAR, "1")
    assert is_enabled() is True
    assert make_scraper().fetch(["ML Engineer"]) == []


def test_is_enabled_defaults_to_false(monkeypatch) -> None:
    monkeypatch.delenv(ENABLE_ENV_VAR, raising=False)
    assert is_enabled() is False


def test_session_cookie_is_never_retained() -> None:
    """A stored cookie is a cookie that can end up in a log or a repr."""
    scraper = make_scraper()
    assert "fake-cookie" not in repr(vars(scraper))
    assert not any(v == "fake-cookie" for v in vars(scraper).values())


def test_linkedin_scraper_has_no_browser_automation_code() -> None:
    """No browser automation path may survive in this module.

    Scanned as parsed AST rather than raw text, so the docstring is free to
    explain why Playwright and the li_at cookie were removed without the
    explanation itself tripping the check.
    """
    import ast
    import inspect

    from nj.scrapers import linkedin

    tree = ast.parse(inspect.getsource(linkedin))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "playwright" not in imported

    # Every string literal outside the docstrings — no cookie name, no
    # linkedin.com URL left to navigate to. Docstring nodes are excluded by
    # identity: ast.get_docstring() returns cleaned text that no longer compares
    # equal to the raw constant, so matching on value would exclude nothing.
    documented = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    docstring_nodes = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, documented)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
        and isinstance(n.body[0].value.value, str)
    }
    literals = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstring_nodes
    ]
    assert not any("li_at" in s for s in literals)
    assert not any("linkedin.com" in s for s in literals)


def test_linkedin_scraper_constructs_without_a_cookie() -> None:
    """Callers that no longer have a cookie to pass must still work."""
    assert LinkedInScraper().fetch(["ML Engineer"]) == []


def test_rate_limiter_can_apply_when_under_limit() -> None:
    assert RateLimiter(max_per_day=5).can_apply() is True


def test_rate_limiter_cannot_apply_when_at_limit() -> None:
    rl = RateLimiter(max_per_day=2)
    rl.record_application()
    rl.record_application()
    assert rl.can_apply() is False


def test_rate_limiter_remaining_decrements() -> None:
    rl = RateLimiter(max_per_day=5)
    assert rl.remaining_today() == 5
    rl.record_application()
    assert rl.remaining_today() == 4


def test_rate_limiter_remaining_never_negative() -> None:
    rl = RateLimiter(max_per_day=1)
    rl.record_application()
    rl.record_application()
    assert rl.remaining_today() == 0


@pytest.mark.asyncio
async def test_rate_limiter_wait_completes() -> None:
    rl = RateLimiter(delay_min=0, delay_max=0)
    await rl.wait()


def test_rate_limiter_counts_from_db_when_repo_given():
    """The daily cap must survive a process restart, or `nj run` x3 sends 3x."""

    class FakeRepo:
        def __init__(self, n):
            self.n = n

        def count_today(self):
            return self.n

    assert RateLimiter(max_per_day=5, repo=FakeRepo(4)).can_apply() is True
    assert RateLimiter(max_per_day=5, repo=FakeRepo(5)).can_apply() is False
    assert RateLimiter(max_per_day=5, repo=FakeRepo(2)).remaining_today() == 3


def test_rate_limiter_fails_closed_if_the_count_errors():
    """A DB failure must not read as 'zero sent today'."""

    class BrokenRepo:
        def count_today(self):
            raise RuntimeError("db gone")

    assert RateLimiter(max_per_day=5, repo=BrokenRepo()).can_apply() is False
