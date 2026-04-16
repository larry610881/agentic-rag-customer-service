"""Transfer to human agent tool.

Returns a channel-agnostic contact card containing a URL (POC stage) or
phone number (future). Each channel renderer (LINE Flex / Web button /
Widget button) is responsible for displaying it to the end user.
"""
from __future__ import annotations

from typing import Any


class TransferToHumanTool:
    """轉接真人客服 / transfer_to_human_agent.

    POC 階段回傳 ``{url, label}``；未來會加 ``phone_number`` 欄位支援
    ``tel:`` 直撥。Tool 本身 channel-agnostic，渲染由各通路負責。
    """

    name = "transfer_to_human_agent"
    description = (
        "轉接真人客服 / transfer to human customer service agent. "
        "當下列情境時請呼叫此工具："
        "① 使用者明確要求轉人工（『要找真人』『轉客服』『叫主管來』）；"
        "② 使用者情緒激動、多次表達不滿或投訴；"
        "③ 複雜退換貨 / 帳務爭議 / 需核對訂單明細等知識庫無法處理的議題；"
        "④ 使用者連問 2 次以上仍未解決問題時。"
        "回傳結果含 context 文字訊息 + contact（由使用者端自動顯示為按鈕）。"
        "**你只需用 context 文字回答即可，不要在回覆中嵌入或提及 URL / 電話號碼。**"
    )

    def __init__(
        self,
        *,
        default_label: str = "聯絡真人客服",
    ) -> None:
        self._default_label = default_label

    async def invoke(
        self,
        *,
        customer_service_url: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Build a contact card payload based on bot.customer_service_url.

        Returns:
            {
              "success": bool,
              "context": str,       # LLM 可直接用的文字訊息
              "contact": {
                "label": str,       # UI button label
                "url": str,         # POC: web URL；未來可能是 tel:
                "type": "url",      # 未來可能 "phone"
              } | None,
            }
        """
        if not customer_service_url:
            # 此 bot 未設定客服資訊：graceful fallback
            return {
                "success": False,
                "context": (
                    "很抱歉，此機器人尚未設定客服聯絡資訊，請稍後再試或直接"
                    "透過網站其他管道聯絡我們。"
                ),
                "contact": None,
            }

        reason_hint = f"（原因：{reason}）" if reason else ""
        return {
            "success": True,
            "context": (
                f"已為您準備轉接真人客服{reason_hint}，請點擊下方「聯絡真人客服」"
                "按鈕繼續。"
            ),
            "contact": {
                "label": self._default_label,
                "url": customer_service_url,
                "type": "url",
            },
        }
