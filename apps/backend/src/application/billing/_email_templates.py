"""Quota Alert Email Templates — S-Token-Gov.3.5

Simple f-string templates rendering both text + HTML for SendGrid.
Future: switch to Jinja2 / MJML if template variants grow.
"""

from __future__ import annotations

from decimal import Decimal

from src.domain.billing.quota_alert import (
    ALERT_TYPE_BASE_EXHAUSTED_100,
    ALERT_TYPE_BASE_WARNING_80,
    QuotaAlertLog,
)
from src.domain.tenant.entity import Tenant


def _format_pct(ratio: Decimal) -> str:
    pct = ratio * Decimal("100")
    return f"{pct:.1f}%"


def render_quota_alert_email(
    alert: QuotaAlertLog,
    tenant: Tenant,
    *,
    dashboard_url: str,
) -> tuple[str, str, str]:
    """Render (subject, text_body, html_body) for one alert."""
    pct = _format_pct(alert.used_ratio)

    if alert.alert_type == ALERT_TYPE_BASE_EXHAUSTED_100:
        subject = f"【AI 客服平台】{tenant.name} 本月 Base 額度已耗盡"
        intro_zh = (
            f"您的本月基礎額度已使用 {pct}，系統會自動續約 addon 包以維持服務不中斷。"
            "請進入後台確認用量趨勢，並評估下個月的方案規劃。"
        )
    elif alert.alert_type == ALERT_TYPE_BASE_WARNING_80:
        subject = f"【AI 客服平台】{tenant.name} 本月額度已使用 {pct}"
        intro_zh = (
            f"您的本月基礎額度已使用 {pct}（達 80% 警示線）。"
            "若用量繼續增加，系統會在額度耗盡時自動續約 addon 包。"
        )
    else:
        # 未來新 alert_type 的 fallback
        subject = f"【AI 客服平台】{tenant.name} 額度警示"
        intro_zh = alert.message or "請進入後台查看詳情。"

    text_body = (
        f"您好，{tenant.name} 管理員：\n\n"
        f"{intro_zh}\n\n"
        f"週期：{alert.cycle_year_month}\n"
        f"訊息：{alert.message}\n"
        f"觸發時間：{alert.created_at:%Y-%m-%d %H:%M UTC}\n\n"
        f"進入後台查看詳情：\n{dashboard_url}\n\n"
        f"此信為系統自動發送，請勿直接回覆。\n"
    )

    html_body = (
        "<html><body style=\"font-family: -apple-system, BlinkMacSystemFont, sans-serif; "
        "color: #333; max-width: 600px; margin: 24px auto; padding: 0 16px;\">"
        f"<h2 style=\"color: #1a1a1a;\">您好，{tenant.name} 管理員</h2>"
        f"<p>{intro_zh}</p>"
        "<table style=\"border-collapse: collapse; margin: 16px 0; width: 100%;\">"
        f"<tr><td style=\"padding: 6px 12px; background: #f5f5f5; width: 100px;\">週期</td>"
        f"<td style=\"padding: 6px 12px;\">{alert.cycle_year_month}</td></tr>"
        f"<tr><td style=\"padding: 6px 12px; background: #f5f5f5;\">使用率</td>"
        f"<td style=\"padding: 6px 12px;\"><strong>{pct}</strong></td></tr>"
        f"<tr><td style=\"padding: 6px 12px; background: #f5f5f5;\">訊息</td>"
        f"<td style=\"padding: 6px 12px;\">{alert.message}</td></tr>"
        f"<tr><td style=\"padding: 6px 12px; background: #f5f5f5;\">觸發時間</td>"
        f"<td style=\"padding: 6px 12px;\">{alert.created_at:%Y-%m-%d %H:%M UTC}</td></tr>"
        "</table>"
        f"<p><a href=\"{dashboard_url}\" "
        "style=\"display:inline-block; background: #2563eb; color: white; "
        "padding: 10px 20px; text-decoration: none; border-radius: 6px;\">"
        "進入後台查看詳情</a></p>"
        "<hr style=\"border: none; border-top: 1px solid #ddd; margin: 24px 0;\">"
        "<p style=\"color: #888; font-size: 12px;\">此信為系統自動發送，請勿直接回覆。</p>"
        "</body></html>"
    )

    return subject, text_body, html_body
