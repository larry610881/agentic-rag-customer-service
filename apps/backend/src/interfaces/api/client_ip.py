"""呼叫端 IP：X-Forwarded-For 尾段（Cloud Run 補真實 IP；與 rate limit 同規則）。"""

from fastapi import Request


def client_ip_of(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else None
