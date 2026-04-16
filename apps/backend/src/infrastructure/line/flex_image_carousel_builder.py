"""LINE Flex Carousel builder — 把 DM 命中圖卡轉為 LINE Flex Message JSON。

LINE Flex carousel 硬限：最多 12 個 bubble。
每個 bubble：hero image + body (page label + caption) + footer button。
所有點擊（圖片本身 + 按鈕）都跳到原圖 GCS signed URL。
"""

from typing import Any

LINE_FLEX_CAROUSEL_MAX = 12


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def build_image_carousel(sources_with_image: list[dict[str, Any]]) -> dict[str, Any]:
    """組 LINE Flex carousel。

    sources_with_image: 每筆需有 image_url（必）、page_number、content_snippet。
    超過 12 筆會被 cap（呼叫方應已先 cap，這裡 double safety）。
    """
    bubbles: list[dict[str, Any]] = []
    for src in sources_with_image[:LINE_FLEX_CAROUSEL_MAX]:
        url = src.get("image_url")
        if not url:
            continue
        page_number = src.get("page_number") or 0
        page_label = f"第 {page_number} 頁" if page_number else "DM 內容"
        caption = _truncate(src.get("content_snippet") or "", 60)

        bubbles.append({
            "type": "bubble",
            "size": "kilo",
            "hero": {
                "type": "image",
                "url": url,
                "size": "full",
                "aspectRatio": "3:4",
                "aspectMode": "cover",
                "action": {"type": "uri", "uri": url},
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": page_label,
                        "weight": "bold",
                        "size": "sm",
                    },
                    {
                        "type": "text",
                        "text": caption,
                        "wrap": True,
                        "size": "xs",
                        "color": "#666666",
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "查看原圖",
                            "uri": url,
                        },
                    },
                ],
            },
        })

    return {"type": "carousel", "contents": bubbles}
