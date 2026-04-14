"""Carrefour MCP Server — 家樂福商品查詢 + 客服轉接

Tools:
  1. search_products — 搜尋家樂福 DM 促銷商品，回傳含線上購物連結的結構化資料
  2. contact_customer_service — 回傳家樂福客服聯絡卡片（電話 + 線上客服連結）
"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Load product data
DATA_PATH = Path(__file__).parent / "data" / "products.json"
_products: list[dict] = []


def _load_products() -> list[dict]:
    global _products
    if _products:
        return _products
    if DATA_PATH.exists():
        with open(DATA_PATH, encoding="utf-8") as f:
            _products = json.load(f)
    return _products


def _search(keywords: list[str], limit: int = 10) -> list[dict]:
    """Simple keyword search across product name, brand, promotion."""
    products = _load_products()
    results = []
    for p in products:
        text = f"{p.get('name', '')} {p.get('brand', '')} {p.get('promotion', '')} {p.get('note', '')}".lower()
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            results.append((score, p))
    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:limit]]


def _make_product_bubble(product: dict) -> dict:
    """Build a LINE Flex Message bubble for a single product."""
    name = product.get("name", "")
    brand = product.get("brand", "")
    price = product.get("price", "")
    promotion = product.get("promotion", "")
    spec = product.get("spec", "")
    image_url = product.get("image_url", "")
    online_url = ""
    matches = product.get("online_matches", [])
    if matches:
        online_url = matches[0].get("url", "")

    # Body contents
    body_contents = [
        {
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "sm",
            "wrap": True,
            "maxLines": 2,
        },
    ]

    if brand and brand != "不詳":
        body_contents.append({
            "type": "text",
            "text": f"品牌：{brand}",
            "size": "xs",
            "color": "#888888",
        })

    if spec:
        body_contents.append({
            "type": "text",
            "text": f"規格：{spec}",
            "size": "xs",
            "color": "#888888",
        })

    # Price + promotion row
    price_contents = []
    if price:
        price_contents.append({
            "type": "text",
            "text": price,
            "size": "md",
            "weight": "bold",
            "color": "#E4002B",
        })
    if promotion and promotion != "無":
        price_contents.append({
            "type": "text",
            "text": promotion,
            "size": "xs",
            "color": "#FFFFFF",
            "background": {"type": "linearGradient", "angle": "0deg", "startColor": "#E4002B", "endColor": "#FF4D4D"},
            "align": "center",
        })

    if price_contents:
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": price_contents,
            "spacing": "sm",
            "margin": "md",
        })

    bubble: dict = {
        "type": "bubble",
        "size": "micro",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "spacing": "sm",
            "paddingAll": "12px",
        },
    }

    # Hero image (if available)
    if image_url:
        bubble["hero"] = {
            "type": "image",
            "url": image_url,
            "size": "full",
            "aspectRatio": "1:1",
            "aspectMode": "cover",
        }

    # Footer with "查看商品" button
    if online_url:
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "查看商品",
                        "uri": online_url,
                    },
                    "style": "primary",
                    "color": "#E4002B",
                    "height": "sm",
                }
            ],
            "paddingAll": "8px",
        }

    return bubble


def _make_customer_service_bubble() -> dict:
    """Build a LINE Flex Message bubble for customer service contact."""
    return {
        "type": "bubble",
        "size": "kilo",
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📞",
                    "size": "3xl",
                    "align": "center",
                },
                {
                    "type": "text",
                    "text": "家樂福客服中心",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center",
                    "margin": "md",
                },
            ],
            "paddingAll": "20px",
            "backgroundColor": "#E4002B10",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "客服專線",
                    "size": "xs",
                    "color": "#888888",
                },
                {
                    "type": "text",
                    "text": "0809-001-365",
                    "size": "xl",
                    "weight": "bold",
                    "margin": "sm",
                },
                {
                    "type": "separator",
                    "margin": "lg",
                },
                {
                    "type": "text",
                    "text": "服務時間：週一至週日 09:00-21:00",
                    "size": "xs",
                    "color": "#888888",
                    "margin": "lg",
                    "wrap": True,
                },
            ],
            "paddingAll": "16px",
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "撥打客服電話",
                        "uri": "tel:0809001365",
                    },
                    "style": "primary",
                    "color": "#E4002B",
                },
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "線上客服",
                        "uri": "https://carrefour.tototalk.com.tw/web-homepage",
                    },
                    "style": "secondary",
                    "margin": "sm",
                },
            ],
            "paddingAll": "12px",
        },
    }


# --- MCP Server ---

import os

_port = int(os.environ.get("PORT", "9001"))

mcp = FastMCP(
    "carrefour",
    instructions="家樂福商品查詢與客服轉接",
    host="0.0.0.0",
    port=_port,
    streamable_http_path="/mcp",
)


@mcp.tool()
def search_products(keywords: str, limit: int = 5) -> str:
    """搜尋家樂福 DM 促銷商品。輸入商品關鍵字（空格分隔多個），回傳含價格、促銷、線上購物連結的商品清單。

    Args:
        keywords: 搜尋關鍵字，空格分隔。例如 "衛生紙 買一送一" 或 "牛奶 鮮乳"
        limit: 回傳筆數上限，預設 5
    """
    kw_list = [k.strip() for k in keywords.split() if k.strip()]
    if not kw_list:
        return json.dumps({"products": [], "message": "請提供搜尋關鍵字"}, ensure_ascii=False)

    results = _search(kw_list, limit=min(limit, 10))

    products_out = []
    flex_bubbles = []
    for p in results:
        matches = p.get("online_matches", [])
        item = {
            "name": p.get("name", ""),
            "brand": p.get("brand", ""),
            "spec": p.get("spec", ""),
            "price": p.get("price", ""),
            "promotion": p.get("promotion", ""),
            "online_url": matches[0]["url"] if matches else "",
        }
        products_out.append(item)
        flex_bubbles.append(_make_product_bubble(p))

    response = {
        "products": products_out,
        "total_found": len(results),
        "flex_carousel": {
            "type": "carousel",
            "contents": flex_bubbles,
        } if flex_bubbles else None,
    }
    return json.dumps(response, ensure_ascii=False)


@mcp.tool()
def contact_customer_service() -> str:
    """取得家樂福客服聯絡資訊。回傳客服電話卡片（含撥打按鈕和線上客服連結）。
    當使用者需要真人客服、投訴、無法由 AI 回答的問題時使用此工具。
    """
    bubble = _make_customer_service_bubble()
    response = {
        "message": "以下是家樂福客服聯絡方式，您可以直接撥打客服專線或使用線上客服：",
        "phone": "0809-001-365",
        "online_url": "https://carrefour.tototalk.com.tw/web-homepage",
        "service_hours": "週一至週日 09:00-21:00",
        "flex_bubble": bubble,
    }
    return json.dumps(response, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
