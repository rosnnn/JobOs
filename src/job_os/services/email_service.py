"""Gmail IMAP/SMTP integration for monitoring replies and account signup."""

from __future__ import annotations

import email
import imaplib
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header
from email.mime.text import MIMEText
from typing import Any

from job_os.config import get_settings
from job_os.services.credentials_service import CredentialsService


class EmailAuthError(Exception):
    """Gmail IMAP login failed — bad app password or IMAP disabled."""


@dataclass
class ParsedEmail:
    message_id: str
    subject: str
    from_address: str
    body_preview: str
    received_at: datetime | None
    raw_headers: dict[str, str]


from job_os.services.email_classifier import EmailClassifier


class GmailService:
    IMAP_HOST = "imap.gmail.com"
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587
    IMAP_FOLDERS = ("INBOX", "[Gmail]/Sent Mail")

    def __init__(self):
        settings = get_settings()
        creds = CredentialsService().load()
        # Profile-saved credentials should take precedence over .env so UI updates apply immediately.
        self._address = creds.get("gmail_address") or settings.gmail_address
        self._password = creds.get("gmail_app_password") or settings.gmail_app_password
        self._classifier = EmailClassifier()

    @property
    def configured(self) -> bool:
        return bool(self._address and self._password)

    @property
    def address(self) -> str | None:
        return self._address

    def _app_password(self) -> str:
        return (self._password or "").replace(" ", "").strip()

    def test_connection(self) -> tuple[bool, str | None]:
        """Verify IMAP login. Returns (ok, error_message)."""
        if not self.configured:
            return False, "Gmail not configured — set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env"
        mail = imaplib.IMAP4_SSL(self.IMAP_HOST)
        try:
            mail.login(self._address, self._app_password())
            mail.select("INBOX")
            return True, None
        except imaplib.IMAP4.error as exc:
            raw = exc.args[0] if exc.args else exc
            msg = raw.decode() if isinstance(raw, bytes) else str(raw)
            if "AUTHENTICATIONFAILED" in msg.upper():
                return False, (
                    "Gmail login failed (invalid App Password). "
                    "Create a new App Password at myaccount.google.com/apppasswords "
                    "(Google Account → Security → 2-Step Verification → App passwords). "
                    "Enable IMAP: Gmail → Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP."
                )
            return False, f"IMAP error: {msg}"
        except Exception as exc:
            return False, str(exc)
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def fetch_recent(self, *, limit: int = 50, since_days: int = 30) -> list[ParsedEmail]:
        if not self.configured:
            return []
        ok, err = self.test_connection()
        if not ok:
            raise EmailAuthError(err or "Gmail authentication failed")
        messages: list[ParsedEmail] = []
        seen: set[str] = set()
        mail = imaplib.IMAP4_SSL(self.IMAP_HOST)
        try:
            mail.login(self._address, self._app_password())
            for folder in self.IMAP_FOLDERS:
                try:
                    status, _ = mail.select(folder)
                    if status != "OK":
                        continue
                except Exception:
                    continue
                _, data = mail.search(None, "ALL")
                ids = data[0].split()
                for num in ids[-limit:]:
                    _, msg_data = mail.fetch(num, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    parsed = self._parse_message(msg)
                    if parsed and parsed.message_id not in seen:
                        seen.add(parsed.message_id)
                        messages.append(parsed)
        finally:
            try:
                mail.logout()
            except Exception:
                pass
        return messages

    def send_email(self, to: str, subject: str, body: str) -> bool:
        if not self.configured:
            return False
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self._address
        msg["To"] = to
        with smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT) as server:
            server.starttls()
            server.login(self._address, self._password.replace(" ", ""))
            server.send_message(msg)
        return True

    def classify(self, subject: str, body: str, from_address: str = "") -> dict[str, Any]:
        return self._classifier.classify(subject, body, from_address)

    def _parse_message(self, msg: email.message.Message) -> ParsedEmail | None:
        subject = self._decode_header(msg.get("Subject", ""))
        from_addr = self._decode_header(msg.get("From", ""))
        message_id = msg.get("Message-ID", f"{from_addr}:{subject}")
        date_str = msg.get("Date")
        received_at: datetime | None = None
        if date_str:
            try:
                received_at = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                received_at = datetime.now(timezone.utc)

        body = self._extract_body(msg)
        headers = {k: str(v) for k, v in msg.items()}
        return ParsedEmail(
            message_id=message_id,
            subject=subject,
            from_address=from_addr,
            body_preview=body[:12000],
            received_at=received_at,
            raw_headers=headers,
        )

    @staticmethod
    def _decode_header(value: str) -> str:
        parts = decode_header(value)
        out = []
        for part, enc in parts:
            if isinstance(part, bytes):
                out.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(part)
        return " ".join(out)

    @staticmethod
    def _extract_body(msg: email.message.Message) -> str:
        plain_parts: list[str] = []
        html_parts: list[str] = []

        def collect(part: email.message.Message) -> None:
            ctype = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                return
            text = payload.decode(errors="replace")
            if ctype == "text/plain":
                plain_parts.append(text)
            elif ctype == "text/html":
                html_parts.append(text)

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                collect(part)
        else:
            collect(msg)

        if plain_parts:
            return max(plain_parts, key=len)
        if html_parts:
            return max(html_parts, key=len)
        return ""
