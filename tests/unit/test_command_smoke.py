"""Every command must survive an empty database.

Five commands — graph, ml, intel, watch, update-role — sat at 0% coverage,
meaning nothing had ever executed them in CI. That is exactly the state the
`nj explain` bug lived in: a code path nobody ran until an operator ran it.

These are smoke tests, not behaviour tests. They assert the weakest useful
thing — that each command runs to completion against a database with no rows
and prints something rather than raising — because a fresh clone is the state
every one of these will first be used in.
"""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console

from nj.models.config import Config


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "smoke.db")


@pytest.fixture
def captured(monkeypatch):
    """Swap each command module's console for one we can read back."""
    buf = StringIO()
    # Wide, so a Rich table elides nothing an assertion is looking for.
    console = Console(file=buf, highlight=False, width=200)

    def use(module_name: str):
        import importlib

        monkeypatch.setattr(f"{module_name}.console", console, raising=False)
        return importlib.import_module(module_name)

    use.buffer = buf  # type: ignore[attr-defined]
    return use


# --- nj graph --------------------------------------------------------------


@pytest.mark.parametrize(
    "subcommand", ["stats", "show", "skills", "companies", "build", "nonsense"]
)
def test_graph_survives_an_empty_database(captured, db, subcommand) -> None:
    module = captured("nj.cli.cmd_graph")
    module.run_graph(Config(), subcommand=subcommand, db_path=db)
    assert captured.buffer.getvalue()


def test_graph_path_without_endpoints_does_not_raise(captured, db) -> None:
    module = captured("nj.cli.cmd_graph")
    module.run_graph(Config(), subcommand="path", query="", target="", db_path=db)


# --- nj ml -----------------------------------------------------------------


@pytest.mark.parametrize("subcommand", ["status", "salary", "nonsense"])
def test_ml_survives_an_untrained_model(captured, db, subcommand) -> None:
    module = captured("nj.cli.cmd_ml")
    module.run_ml(Config(), subcommand=subcommand, role="ML Engineer", db_path=db)
    assert captured.buffer.getvalue()


def test_ml_predict_without_training_data_explains_itself(captured, db) -> None:
    """No model on disk is the normal state, not an error."""
    module = captured("nj.cli.cmd_ml")
    module.run_ml(Config(), subcommand="predict", company="Acme", role="ML", db_path=db)
    assert captured.buffer.getvalue()


def test_ml_semantic_with_no_such_job(captured, db) -> None:
    module = captured("nj.cli.cmd_ml")
    module.run_ml(Config(), subcommand="semantic", job_id="nope", db_path=db)


# --- nj intel --------------------------------------------------------------


@pytest.mark.parametrize("subcommand", [None, "help", "nonsense"])
def test_intel_help_paths(captured, db, subcommand) -> None:
    module = captured("nj.cli.cmd_intel")
    module.run_intel(subcommand=subcommand, db_path=db)
    assert captured.buffer.getvalue()


@pytest.mark.parametrize("subcommand", ["company", "top", "role"])
def test_intel_queries_against_no_petition_data(captured, db, subcommand) -> None:
    """87,595 companies is the loaded state; zero is the fresh-clone state."""
    module = captured("nj.cli.cmd_intel")
    module.run_intel(subcommand=subcommand, query="Amazon", db_path=db)
    assert captured.buffer.getvalue()


def test_intel_company_without_a_name_asks_for_one(captured, db) -> None:
    module = captured("nj.cli.cmd_intel")
    module.run_intel(subcommand="company", query="", db_path=db)
    assert "Usage" in captured.buffer.getvalue()


# --- nj watch --------------------------------------------------------------


def test_watch_without_gmail_credentials_does_not_raise(captured, db, monkeypatch) -> None:
    module = captured("nj.cli.cmd_watch")
    monkeypatch.setattr(
        "nj.integrations.gmail_watcher.check_callbacks",
        lambda *a, **k: [],
    )
    module.run_watch(Config(), db_path=db, dry_run=True)
    assert captured.buffer.getvalue()


def test_watch_reports_a_callback_without_touching_the_database(captured, db, monkeypatch) -> None:
    module = captured("nj.cli.cmd_watch")
    monkeypatch.setattr(
        "nj.integrations.gmail_watcher.check_callbacks",
        lambda *a, **k: [
            {
                # The company is read off the matched application, not the
                # email — the watcher's job is to tie a message back to a row.
                "application": SimpleNamespace(company="Acme", id="app-1"),
                "subject": "Next steps",
                "signal": "interview",
                "date": "2026-08-18",
                "snippet": "We would like to schedule a call.",
            }
        ],
    )
    module.run_watch(Config(), db_path=db, dry_run=True)
    output = captured.buffer.getvalue()
    assert "Acme" in output
    assert "INTERVIEW" in output


# --- nj update-role --------------------------------------------------------


def test_update_role_without_a_cv_explains_itself(captured, tmp_path, monkeypatch) -> None:
    module = captured("nj.cli.cmd_update_role")
    monkeypatch.chdir(tmp_path)
    module.run_update_role(Config())
    assert captured.buffer.getvalue()
