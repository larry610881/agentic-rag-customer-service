"""伺服器簽發的 widget visitor id（Issue #67 P4）

格式 ``<uuid>.<hmac16>``。widget 端只能拿回伺服器發過的值；自報別人的 visitor id
（想讀他人記憶）簽章不符 → 視為新訪客。
"""

import hashlib
import hmac
from uuid import uuid4

_SIG_LEN = 16


class VisitorIdSigner:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def _sign(self, raw: str) -> str:
        return hmac.new(self._secret, raw.encode("utf-8"), hashlib.sha256).hexdigest()[
            :_SIG_LEN
        ]

    def issue(self) -> str:
        raw = str(uuid4())
        return f"{raw}.{self._sign(raw)}"

    def verify(self, value: str | None) -> str | None:
        """回傳未簽章的 raw id；格式錯或簽章不符回 None。"""
        if not value or "." not in value:
            return None
        raw, sig = value.rsplit(".", 1)
        if not raw or not hmac.compare_digest(sig, self._sign(raw)):
            return None
        return raw
