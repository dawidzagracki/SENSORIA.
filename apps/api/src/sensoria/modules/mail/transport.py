"""SMTP transport; works with any relay (Postmark, SES, Resend, own server)."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Protocol

from sensoria.config import Settings


@dataclass(frozen=True, slots=True)
class OutgoingMail:
    message_id: str
    to: str
    subject: str
    html: str
    text: str
    attachments: list[tuple[str, bytes, str]]


class TransientMailError(Exception):
    """Retryable provider problem (timeout, 4xx)."""


class PermanentMailError(Exception):
    """Rejected message (bad recipient, 5xx); do not retry."""


class MailTransport(Protocol):
    async def send(self, mail: OutgoingMail) -> str: ...


def mail_configured(settings: Settings) -> bool:
    return bool(settings.SMTP_HOST and settings.MAIL_FROM)


class SMTPTransport:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _send_blocking(self, mail: OutgoingMail) -> str:
        s = self.settings
        assert s.SMTP_HOST and s.MAIL_FROM
        message = EmailMessage()
        message["From"] = s.MAIL_FROM
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = mail.message_id
        if s.MAIL_REPLY_TO:
            message["Reply-To"] = s.MAIL_REPLY_TO
        message.set_content(mail.text)
        message.add_alternative(mail.html, subtype="html")
        for name, content, mime in mail.attachments:
            main, _, sub = mime.partition("/")
            message.add_attachment(
                content, maintype=main, subtype=sub or "octet-stream", filename=name
            )
        try:
            with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=20) as client:
                if s.SMTP_STARTTLS:
                    client.starttls(context=ssl.create_default_context())
                if s.SMTP_USERNAME and s.SMTP_PASSWORD:
                    client.login(s.SMTP_USERNAME, s.SMTP_PASSWORD.get_secret_value())
                client.send_message(message)
        except smtplib.SMTPRecipientsRefused as error:
            raise PermanentMailError("recipient_refused") from error
        except smtplib.SMTPResponseException as error:
            if 500 <= error.smtp_code < 600:
                raise PermanentMailError(f"smtp_{error.smtp_code}") from error
            raise TransientMailError(f"smtp_{error.smtp_code}") from error
        except (OSError, smtplib.SMTPException) as error:
            raise TransientMailError(type(error).__name__) from error
        return mail.message_id

    async def send(self, mail: OutgoingMail) -> str:
        return await asyncio.to_thread(self._send_blocking, mail)


def new_message_id(domain_hint: str = "sensoria.shop") -> str:
    return make_msgid(domain=domain_hint)
