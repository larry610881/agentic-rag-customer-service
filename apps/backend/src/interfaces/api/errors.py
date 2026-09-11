"""統一錯誤回應契約（Issue #94）。

所有 4xx / 5xx 的 body 固定為：

    {"detail": <str>, "code": <str>, "request_id": <str | None>, ...extra}

- ``detail``：給人看的訊息，可變、可翻譯，客戶端不得據此分支。
- ``code``：穩定的機器可讀碼（snake_case），客戶端據此分支。
- ``request_id``：與 ``X-Request-ID`` 標頭同值，供客戶端回報。
- 422 另附 ``errors``（FastAPI 原始驗證細節陣列）；``detail`` 仍為字串，
  避免同一個 key 在不同狀態碼是兩種型別（原生 client 共用 error model 會解碼失敗）。

``HTTPException(detail="insufficient_scope")`` 這類 detail 本身已是 code 的既有寫法
維持相容：``infer_code`` 會直接沿用；detail 為句子時依狀態碼給通用 code。
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

_CODE_BY_STATUS: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "request_timeout",
}

# FastAPI / Starlette 自己產生的 detail 文案 → 穩定 code
_CODE_BY_KNOWN_DETAIL: dict[str, str] = {
    "Not authenticated": "token_missing",
    "Invalid authentication credentials": "token_invalid",
    "Not Found": "not_found",
    "Method Not Allowed": "method_not_allowed",
}


class ApiError(HTTPException):
    """帶穩定 ``code`` 的 HTTPException。``message`` 省略時 detail 即為 code。"""

    def __init__(
        self,
        status_code: int,
        *,
        code: str,
        message: str | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code, detail=message or code, headers=headers
        )
        self.code = code
        self.extra = extra or {}


def current_request_id() -> str | None:
    """RequestIDMiddleware 以 structlog contextvars 綁定的 request_id。"""
    value = structlog.contextvars.get_contextvars().get("request_id")
    return str(value) if value else None


def infer_code(status_code: int, detail: Any) -> str:
    if isinstance(detail, str):
        if _CODE_RE.match(detail):
            return detail
        known = _CODE_BY_KNOWN_DETAIL.get(detail)
        if known:
            return known
    return _CODE_BY_STATUS.get(status_code, "error")


def error_body(
    status_code: int,
    detail: str,
    *,
    code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "detail": detail,
        "code": code or infer_code(status_code, detail),
        "request_id": current_request_id(),
    }
    if extra:
        body.update(extra)
    return body


def _detail_text(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict) and isinstance(detail.get("detail"), str):
        return str(detail["detail"])
    return str(detail)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = getattr(exc, "code", None)
    extra = dict(getattr(exc, "extra", None) or {})
    if isinstance(exc.detail, dict):
        # 既有寫法 detail 帶 dict（含 retry_after 等）→ 攤平成 extra
        flattened = {k: v for k, v in exc.detail.items() if k != "detail"}
        extra = {**flattened, **extra}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            exc.status_code, _detail_text(exc.detail), code=code, extra=extra
        ),
        headers=getattr(exc, "headers", None),
    )


def _validation_summary(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return "Request validation failed"
    first = errors[0]
    loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    msg = first.get("msg", "invalid value")
    where = f" at '{loc}'" if loc else ""
    more = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
    return f"Request validation failed{where}: {msg}{more}"


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=422,
        content=error_body(
            422,
            _validation_summary(errors),
            code="validation_error",
            extra={"errors": errors},
        ),
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        StarletteHTTPException, http_exception_handler  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler  # type: ignore[arg-type]
    )
