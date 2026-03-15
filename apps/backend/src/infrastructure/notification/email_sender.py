"""Email notification sender using aiosmtplib."""

import json
from email.message import EmailMessage

import aiosmtplib
import structlog

from src.domain.observability.notification import (
    NotificationChannel,
    NotificationSender,
)

_logger = structlog.get_logger(__name__)


class EmailNotificationSender(NotificationSender):
    """Sends email notifications via SMTP."""

    def __init__(
        self,
        default_smtp_host: str = "localhost",
        default_smtp_port: int = 587,
    ) -> None:
        self._default_host = default_smtp_host
        self._default_port = default_smtp_port

    def channel_type(self) -> str:
        return "email"

    async def send(
        self, channel: NotificationChannel, subject: str, body: str
    ) -> None:
        try:
            config = json.loads(channel.config_encrypted)
        except (json.JSONDecodeError, TypeError):
            config = {}

        smtp_host = config.get("smtp_host", self._default_host)
        smtp_port = config.get("smtp_port", self._default_port)
        username = config.get("username", "")
        password = config.get("password", "")
        from_addr = config.get("from", username)
        recipients = config.get("recipients", [])

        if not recipients:
            _logger.warning(
                "email_sender.no_recipients", channel_id=channel.id
            )
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=username or None,
            password=password or None,
            start_tls=True,
        )
