"""SendGrid Quota Alert Sender — S-Token-Gov.3.5

Sends quota alert emails via SendGrid HTTP API. Wraps the sync SendGrid
SDK with asyncio.to_thread to avoid blocking the worker event loop.

Why HTTP API instead of SMTP:
- POC VM outbound IP often hits spam filters
- Status_code immediately available (no SMTP greeting parsing)
- SendGrid free tier 100 emails/day enough for POC
"""

from __future__ import annotations

import asyncio
import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, To

from src.domain.billing.email_sender import QuotaAlertEmailSender

logger = logging.getLogger(__name__)


class SendGridQuotaAlertSender(QuotaAlertEmailSender):
    def __init__(
        self,
        api_key: str,
        from_email: str,
        from_name: str,
    ) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._from_name = from_name

    async def send(
        self,
        *,
        to_email: str,
        to_name: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        if not self._api_key:
            raise RuntimeError(
                "SendGrid API key not configured (SENDGRID_API_KEY)"
            )

        message = Mail(
            from_email=Email(self._from_email, self._from_name),
            to_emails=To(to_email, to_name),
            subject=subject,
        )
        message.add_content(Content("text/plain", text_body))
        message.add_content(Content("text/html", html_body))

        client = SendGridAPIClient(self._api_key)
        # SendGrid SDK is sync; offload to thread to keep loop responsive
        response = await asyncio.to_thread(client.send, message)

        if response.status_code >= 300:
            raise RuntimeError(
                f"SendGrid {response.status_code}: {response.body!r}"
            )
        logger.info(
            "sendgrid.quota_alert.sent",
            extra={"to": to_email, "status": response.status_code},
        )
