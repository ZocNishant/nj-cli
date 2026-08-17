from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from nj.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

INTERVIEW_SIGNALS = [
    "interview",
    "next steps",
    "schedule",
    "call",
    "meet",
    "meeting",
    "chat",
    "opportunity",
    "move forward",
    "moving forward",
    "pleased to",
    "would like to",
    "invite you",
    "spoken with",
    "recruiter",
    "hiring manager",
    "technical screen",
    "phone screen",
    "video call",
    "zoom",
    "teams meeting",
]

REJECTION_SIGNALS = [
    "unfortunately",
    "regret to inform",
    "not moving forward",
    "other candidates",
    "not selected",
    "position has been filled",
    "decided to move",
    "will not be",
    "not a fit",
    "keep your resume on file",
    "future opportunities",
    "won't be moving",
    "decided not to",
]

OFFER_SIGNALS = [
    "offer",
    "pleased to offer",
    "extend an offer",
    "compensation",
    "salary",
    "start date",
    "onboard",
    "welcome to the team",
    "congratulations",
]


class CallbackSignal:
    INTERVIEW = "interview"
    REJECTION = "rejection"
    OFFER = "offer"
    UNKNOWN = "unknown"


def detect_signal(subject: str, body: str) -> str:
    text = (subject + " " + body).lower()
    for signal in OFFER_SIGNALS:
        if signal in text:
            return CallbackSignal.OFFER
    for signal in INTERVIEW_SIGNALS:
        if signal in text:
            return CallbackSignal.INTERVIEW
    for signal in REJECTION_SIGNALS:
        if signal in text:
            return CallbackSignal.REJECTION
    return CallbackSignal.UNKNOWN


def check_callbacks(
    db_path: str = "data/nj.db",
    days_back: int = 7,
    credentials_path: str = "gmail_credentials.json",
    token_path: str = ".gmail_token.json",
) -> list[dict]:
    from nj.db.repos.application_repo import ApplicationRepo

    app_repo = ApplicationRepo(db_path)
    apps = app_repo.get_applications()
    if not apps:
        return []

    company_to_app = {a.company.lower(): a for a in apps if hasattr(a, "company") and a.company}

    service = _get_gmail_service(credentials_path, token_path)
    if not service:
        return []

    since = datetime.now(UTC) - timedelta(days=days_back)
    query = f"after:{since.strftime('%Y/%m/%d')}"

    try:
        result = service.users().messages().list(userId="me", q=query, maxResults=100).execute()
        messages = result.get("messages", [])
    except Exception as e:
        logger.warning("gmail_list_failed", error=str(e))
        return []

    callbacks = []
    for msg_ref in messages:
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_ref["id"], format="full")
                .execute()
            )
        except Exception as e:
            logger.warning("gmail_fetch_failed", msg_id=msg_ref["id"], error=str(e))
            continue

        subject = _get_header(msg, "Subject") or ""
        sender = _get_header(msg, "From") or ""
        body = _extract_email_body(msg)
        signal = detect_signal(subject, body)

        if signal == CallbackSignal.UNKNOWN:
            continue

        matched_app = None
        for company_key, app in company_to_app.items():
            if company_key in sender.lower() or company_key in subject.lower():
                matched_app = app
                break

        callbacks.append(
            {
                "signal": signal,
                "subject": subject,
                "sender": sender,
                "application": matched_app,
                "message_id": msg_ref["id"],
            }
        )
        logger.info(
            "callback_detected",
            signal=signal,
            subject=subject[:60],
            company=matched_app.company if matched_app else "unknown",
        )

    return callbacks


def update_application_statuses(
    callbacks: list[dict],
    db_path: str = "data/nj.db",
) -> int:
    from nj.db.repos.application_repo import ApplicationRepo
    from nj.models.application import ApplicationStatus, OutcomeType

    if not callbacks:
        return 0

    app_repo = ApplicationRepo(db_path)
    updated = 0

    signal_to_status = {
        CallbackSignal.INTERVIEW: ApplicationStatus.INTERVIEWING,
        CallbackSignal.OFFER: ApplicationStatus.OFFERED,
        CallbackSignal.REJECTION: ApplicationStatus.REJECTED,
    }
    signal_to_outcome = {
        CallbackSignal.INTERVIEW: OutcomeType.INTERVIEW,
        CallbackSignal.OFFER: OutcomeType.OFFER,
        CallbackSignal.REJECTION: OutcomeType.REJECTION,
    }

    for cb in callbacks:
        app = cb.get("application")
        signal = cb.get("signal")
        if not app or signal == CallbackSignal.UNKNOWN:
            continue
        new_status = signal_to_status.get(signal)
        if not new_status:
            continue
        try:
            app_repo.update_status(app.id, new_status)
            outcome = signal_to_outcome.get(signal)
            if outcome:
                app_repo.record_outcome(app.job_id, outcome)
            updated += 1
            logger.info(
                "application_status_updated",
                app_id=app.id,
                company=app.company,
                new_status=new_status,
            )
            try:
                from nj.db.repos.job_repo import JobRepo
                from nj.graph.builder import GraphBuilder

                builder = GraphBuilder(db_path=db_path)
                job_repo = JobRepo(db_path)
                jobs = job_repo.get_jobs()
                job = next((j for j in jobs if j.id == app.job_id), None)
                if job:
                    builder.add_job_application(
                        job_title=job.title,
                        company=job.company,
                        score=0,
                        matched_skills=[],
                        missing_skills=[],
                        outcome=cb["signal"],
                    )
            except Exception:
                pass
        except Exception as e:
            logger.warning("status_update_failed", app_id=app.id, error=str(e))

    return updated


def _get_gmail_service(
    credentials_path: str = "gmail_credentials.json",
    token_path: str = ".gmail_token.json",
):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning(
            "gmail_deps_missing",
            hint="pip install google-auth google-auth-oauthlib google-api-python-client",
        )
        return None

    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    creds = None

    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("gmail_token_refresh_failed", error=str(e))
                creds = None

        if not creds:
            if not Path(credentials_path).exists():
                logger.warning("gmail_credentials_missing", path=credentials_path)
                return None
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        Path(token_path).write_text(creds.to_json())

    try:
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.warning("gmail_build_failed", error=str(e))
        return None


def _extract_email_body(msg: dict) -> str:
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])

    if not parts:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return ""

    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    for part in parts:
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                raw = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                from nj.utils.text import clean_html

                return clean_html(raw)

    return ""


def _get_header(msg: dict, name: str) -> str | None:
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None
