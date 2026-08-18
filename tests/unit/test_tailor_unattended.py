"""`nj run` must say what it will do, and honour what it was told.

`apply.automation_phase` was an integer read at exactly one place, and at its
default of 1 the command could never produce a CV — which made the four stages
after it unreachable, with nothing in the name to hint at that. "Phase" also
implied a progression toward auto-submission the project has abandoned.
"""

from __future__ import annotations

from nj.models.config import ApplyConfig, Config


def test_the_default_is_to_queue_not_tailor() -> None:
    assert ApplyConfig().tailor_unattended is False


def test_a_legacy_phase_1_config_still_queues() -> None:
    assert ApplyConfig(**{"automation_phase": 1}).tailor_unattended is False


def test_a_legacy_phase_2_config_still_tailors() -> None:
    """Someone who asked for unattended tailoring must not quietly stop getting it."""
    assert ApplyConfig(**{"automation_phase": 2}).tailor_unattended is True


def test_a_nonsense_legacy_value_falls_back_to_the_safe_default() -> None:
    assert ApplyConfig(**{"automation_phase": "banana"}).tailor_unattended is False


def test_an_explicit_setting_wins_over_the_legacy_key() -> None:
    config = ApplyConfig(**{"automation_phase": 1, "tailor_unattended": True})
    assert config.tailor_unattended is True


def test_a_full_config_round_trips_the_legacy_key() -> None:
    config = Config(**{"apply": {"automation_phase": 2, "enabled": True}})
    assert config.apply.tailor_unattended is True
    assert config.apply.enabled is True


def test_the_flag_is_not_a_submit_switch() -> None:
    """Whatever it is set to, nothing in the pipeline may write SUBMITTED."""
    import inspect

    from nj.cli import cmd_run
    from nj.models.application import ApplicationStatus

    source = inspect.getsource(cmd_run)
    assert "ApplicationStatus.SUBMITTED" not in source
    assert ApplicationStatus.GENERATED.value == "generated"


def test_run_pipeline_takes_an_explicit_override() -> None:
    import inspect

    from nj.cli.cmd_run import run_pipeline

    params = inspect.signature(run_pipeline).parameters
    assert "tailor" in params
    assert params["tailor"].default is None


def test_the_cli_exposes_the_flag() -> None:
    import inspect

    from nj.cli.app import run

    assert "tailor" in inspect.signature(run).parameters
