"""Quota Alert Email Sender ABC — S-Token-Gov.3.5

Domain port for sending one quota alert email. Implementation may be
SendGrid HTTP API, SMTP, or local MailHog (test fixture).

failure -> raise exception (caller decides retry policy).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class QuotaAlertEmailSender(ABC):
    @abstractmethod
    async def send(
        self,
        *,
        to_email: str,
        to_name: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        """寄一封警示信。失敗 raise；caller (use case) try/except 處理。"""
        ...
