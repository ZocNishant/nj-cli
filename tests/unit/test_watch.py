from __future__ import annotations

from nj.integrations.gmail_watcher import CallbackSignal, detect_signal


def test_detect_interview_signal() -> None:
    result = detect_signal("Interview invitation", "We would like to schedule an interview.")
    assert result == CallbackSignal.INTERVIEW


def test_detect_rejection_signal() -> None:
    result = detect_signal(
        "Application update",
        "We regret to inform you that we have selected other candidates for this role.",
    )
    assert result == CallbackSignal.REJECTION


def test_detect_offer_signal() -> None:
    result = detect_signal("Job offer", "We are pleased to extend an offer with a salary of $120k.")
    assert result == CallbackSignal.OFFER


def test_detect_unknown_signal() -> None:
    result = detect_signal("Thank you", "We received your application.")
    assert result == CallbackSignal.UNKNOWN


def test_detect_signal_case_insensitive() -> None:
    result = detect_signal("INTERVIEW INVITATION", "We'd like to SCHEDULE a call.")
    assert result == CallbackSignal.INTERVIEW


def test_detect_zoom_signal() -> None:
    result = detect_signal("Next steps", "Please join a Zoom video call with our team.")
    assert result == CallbackSignal.INTERVIEW


def test_detect_salary_signal() -> None:
    result = detect_signal("Exciting news", "We'd like to discuss compensation and start date.")
    assert result == CallbackSignal.OFFER


def test_offer_beats_interview() -> None:
    result = detect_signal(
        "Offer and next steps",
        "Congratulations! We'd like to schedule an onboarding meeting.",
    )
    assert result == CallbackSignal.OFFER


def test_detect_rejection_keep_on_file() -> None:
    result = detect_signal(
        "Your application",
        "We will keep your resume on file for future opportunities.",
    )
    assert result == CallbackSignal.REJECTION


def test_detect_phone_screen_signal() -> None:
    result = detect_signal(
        "Phone screen invitation",
        "Our recruiter would like to conduct a phone screen.",
    )
    assert result == CallbackSignal.INTERVIEW
