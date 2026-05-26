from __future__ import annotations

import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from nj.models.config import NotifyConfig
from nj.notify.base import BaseNotifier
from nj.notify.digest import format_summary_table
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class EmailNotifier(BaseNotifier):
    def __init__(self, config: NotifyConfig):
        self.config = config

    def send_application_email(
        self,
        job_title: str,
        company: str,
        job_url: str,
        score: int,
        confidence: float,
        matched_skills: list[str],
        missing_skills: list[str],
        visa_label: str,
        visa_notes: str,
        cv_path: str | None = None,
        cover_letter_path: str | None = None,
    ) -> bool:
        subject = f"nj applied: {job_title} @ {company} | score {score}"
        matched_str = ", ".join(matched_skills[:8]) or "none"
        missing_str = ", ".join(missing_skills[:5]) or "none"
        body = (
            f"Job: {job_title}\n"
            f"Company: {company}\n"
            f"URL: {job_url}\n\n"
            f"Score: {score}/100 (confidence: {confidence:.2f})\n\n"
            f"Matched skills: {matched_str}\n"
            f"Missing skills: {missing_str}\n\n"
            f"Visa: {visa_label} — {visa_notes}\n\n"
            f"Tailored CV and cover letter attached."
        )
        attachments = []
        if cv_path and Path(cv_path).exists():
            attachments.append(cv_path)
        if cover_letter_path and Path(cover_letter_path).exists():
            attachments.append(cover_letter_path)
        return self._send(subject, body, attachments)

    def send_daily_summary(self, applications: list[dict]) -> bool:
        import datetime as _dt

        subject = (
            f"nj daily: {len(applications)} applications | "
            f"{_dt.datetime.now().strftime('%Y-%m-%d')}"
        )
        body = format_summary_table(applications)
        return self._send(subject, body, attachments=[])

    def _send(
        self,
        subject: str,
        body: str,
        attachments: list[str],
    ) -> bool:
        if not self.config.email_to:
            logger.warning("email_skipped_no_recipient")
            return False
        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_user
            msg["To"] = self.config.email_to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            for path in attachments:
                self._attach_file(msg, path)
            if self.config.provider == "sendgrid":
                return self._send_sendgrid(msg, subject, body)
            return self._send_smtp(msg)
        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            return False

    def _send_smtp(self, msg: MIMEMultipart) -> bool:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            server.starttls(context=ctx)
            server.login(self.config.smtp_user, self.config.smtp_password)
            server.send_message(msg)
        logger.info("email_sent_smtp", to=self.config.email_to, subject=msg["Subject"])
        return True

    def _send_sendgrid(
        self,
        msg: MIMEMultipart,
        subject: str,
        body: str,
    ) -> bool:
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail

            sg = sendgrid.SendGridAPIClient(api_key=self.config.sendgrid_api_key)
            mail = Mail(
                from_email=self.config.smtp_user,
                to_emails=self.config.email_to,
                subject=subject,
                plain_text_content=body,
            )
            sg.send(mail)
            logger.info("email_sent_sendgrid", to=self.config.email_to)
            return True
        except ImportError:
            logger.warning("sendgrid_not_installed_falling_back_to_smtp")
            return self._send_smtp(msg)
        except Exception as e:
            logger.error("sendgrid_send_failed", error=str(e))
            return False

    def _attach_file(self, msg: MIMEMultipart, path: str) -> None:
        p = Path(path)
        if not p.exists():
            logger.warning("attachment_not_found", path=path)
            return
        with open(p, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={p.name}",
        )
        msg.attach(part)
