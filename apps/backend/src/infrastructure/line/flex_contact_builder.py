"""LINE Flex Message builder for the `transfer_to_human_agent` tool's contact card.

Single bubble with a primary URI button. POC 階段 URL 為客服頁面，未來
``type=phone`` 會改走 ``tel:`` action。
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _force_external_browser(url: str) -> str:
    """對網頁 URL 附加 LINE 官方 ``openExternalBrowser=1`` 參數。

    Android 的 LINE in-app WebView 不會彈出電話/麥克風授權視窗，
    客服頁的網路電話會卡住；強制外部瀏覽器開啟才能正常請求授權。
    """
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["openExternalBrowser"] = "1"
    return urlunsplit(parts._replace(query=urlencode(query)))


def build_contact_flex(contact: dict[str, Any]) -> dict[str, Any]:
    """Build a LINE Flex bubble with a single CTA button.

    Args:
        contact: {"label": str, "url": str, "type": "url" | "phone"}

    Returns:
        Flex JSON contents (single bubble) suitable for LINE Messaging API.
    """
    label = str(contact.get("label") or "聯絡客服")
    url = str(contact.get("url") or "")
    contact_type = contact.get("type", "url")

    # 未來 phone 型別改走 tel: action；POC 階段一律走 URI
    if contact_type == "phone":
        action_uri = url if url.startswith("tel:") else f"tel:{url}"
    else:
        action_uri = _force_external_browser(url)

    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "需要真人客服協助嗎？",
                    "weight": "bold",
                    "size": "md",
                    "color": "#1f2937",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": "點擊下方按鈕可轉接真人客服。",
                    "size": "sm",
                    "color": "#6b7280",
                    "wrap": True,
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": label[:20],  # LINE label 上限 20 字元
                        "uri": action_uri,
                    },
                }
            ],
        },
    }
