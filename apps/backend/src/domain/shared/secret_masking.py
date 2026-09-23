"""API 回應中的憑證遮罩（Issue #102）。

MCP 憑證正確的放法是 env_values + ``{KEY}`` 佔位符（回應時已遮罩）；但網址與 stdio
參數是自由文字，若有人把 token 直接寫進去，回應不可原樣吐出。

- ``mask_url``：網址帳密段、名稱像憑證的查詢參數值 → ``***``
- ``mask_args``：``--token x`` / ``--api-key=x`` / ``API_SECRET=x`` → ``***``
- ``{NAME}`` 佔位符不是憑證，保留給後台看模板
- 沒有需要遮罩的內容時原樣回傳（不重新編碼網址）
- ``keep_if_masked``：表單把遮罩後的值原封送回時保留舊值（同 LINE 憑證慣例）
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urlsplit, urlunsplit

MASK = "***"

_SECRET_NAME = re.compile(
    r"(token|secret|passw|pwd|api[_-]?key|apikey|access[_-]?key|private[_-]?key"
    r"|auth|credential|signature|sig$|session)",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"^\{[A-Za-z_][A-Za-z0-9_]*\}$")

T = TypeVar("T")


def _is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME.search(name.lstrip("-")))


def _maskable(value: str) -> bool:
    return bool(value) and value != MASK and not _PLACEHOLDER.match(value)


def mask_url(url: str) -> str:
    if not url:
        return url
    parts = urlsplit(url)
    changed = False

    netloc = parts.netloc
    if "@" in netloc:
        userinfo, host = netloc.rsplit("@", 1)
        user, sep, password = userinfo.partition(":")
        if sep and _maskable(password):
            netloc, changed = f"{user}:{MASK}@{host}", True
        elif not sep and _maskable(user):
            netloc, changed = f"{MASK}@{host}", True

    query_items = parts.query.split("&") if parts.query else []
    masked_query = []
    for item in query_items:
        key, sep, value = item.partition("=")
        if sep and _is_secret_name(key) and _maskable(value):
            masked_query.append(f"{key}={MASK}")
            changed = True
        else:
            masked_query.append(item)

    if not changed:
        return url
    return urlunsplit(
        (parts.scheme, netloc, parts.path, "&".join(masked_query), parts.fragment)
    )


def mask_args(args: list[str]) -> list[str]:
    masked: list[str] = []
    mask_next = False
    for arg in args:
        if mask_next:
            masked.append(MASK if _maskable(arg) else arg)
            mask_next = False
            continue
        name, sep, value = arg.partition("=")
        if sep and _is_secret_name(name) and _maskable(value):
            masked.append(f"{name}={MASK}")
        else:
            masked.append(arg)
            # --token <value>：旗標本身不帶值時，下一個參數是憑證
            mask_next = not sep and arg.startswith("-") and _is_secret_name(arg)
    return masked


def keep_if_masked(incoming: T, existing: T, masker: Callable[[T], T]) -> T:
    """incoming 等於 existing 遮罩後的樣子 → 使用者沒改，保留 existing。"""
    if existing and incoming == masker(existing) and incoming != existing:
        return existing
    return incoming
