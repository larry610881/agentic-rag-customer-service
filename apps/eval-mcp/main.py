"""評測用自架 MCP 伺服器 —— 三個「確定性」工具。

為什麼自架而不是串現成的開源 MCP：
評測要的是可重現。第三方 MCP 有網路抖動、限流與回應變動，模型明明選對工具卻拿到
逾時，分數會掉在跟模型能力無關的地方。這裡的三個工具回傳固定資料，同一個輸入永遠
同一個輸出，工具選對與否才是唯一的變因。

三個工具各自製造一種難度：

1. ``get_today``      —— 讓「這期 DM 還剩幾天」變成必須「DM 圖卡工具 + 本工具」
                         兩個一起用才算得出來的多工具題。
2. ``get_store_hours``—— 跟 ``rag_query`` 高度重疊的**干擾項**。營業時間知識庫也查得到，
                         看模型會不會被工具名稱吸引而放棄檢索。
3. ``get_order_status``—— 讓「帳單金額對不上」這題的正解從「轉真人」變成「查訂單」。
                         同一題在有無此工具時正解不同，這是測「工具感知」最乾淨的設計。

認證：後端的 MCP client 用 ``streamablehttp_client(url)``，**不送自訂 header**，
所以只能把密鑰放在網址路徑（``MCP_PATH_TOKEN``）。這裡的工具全是唯讀假資料，
路徑密鑰足夠；真要接敏感資料的 MCP 必須先讓 client 支援 header 認證。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

TPE = timezone(timedelta(hours=8))

mcp = FastMCP("eval-tools", instructions="萬家福／樂家康客服的輔助工具（評測用固定資料）")

# --- 固定資料 -------------------------------------------------------------
_STORE_HOURS: dict[str, str] = {
    "重新": "10:00–24:00",
    "內湖": "10:00–23:00",
    "板橋": "10:00–24:00",
    "中壢": "09:00–23:00",
    "文心": "10:00–23:00",
    "屏東": "10:00–22:30",
    "花蓮": "10:00–22:00",
}

_ORDERS: dict[str, dict[str, str]] = {
    "A20260815001": {
        "狀態": "已完成", "下單日": "2026-08-15", "金額": "3,280 元",
        "付款方式": "信用卡", "備註": "含家電延長保固 199 元",
    },
    "A20260901007": {
        "狀態": "配送中", "下單日": "2026-09-01", "金額": "1,150 元",
        "付款方式": "APP 錢包", "備註": "預計 2026-09-10 送達",
    },
    "A20260903012": {
        "狀態": "退貨處理中", "下單日": "2026-09-03", "金額": "899 元",
        "付款方式": "信用卡", "備註": "退款將於 7 個工作天內退回原卡",
    },
}

# 當期 DM 檔期（myEDM「采集漫旅」2026/9/1–9/15）
_DM_START, _DM_END = "2026-09-01", "2026-09-15"


@mcp.tool()
def get_today() -> dict:
    """取得今天的日期、星期與台北時間。

    需要計算「還剩幾天」「這期活動到什麼時候」「上個月是幾月」這類問題時使用。
    知識庫是靜態文件，不會知道今天是哪一天。
    """
    now = datetime.now(TPE)
    end = datetime.strptime(_DM_END, "%Y-%m-%d").replace(tzinfo=TPE)
    days_left = (end.date() - now.date()).days
    return {
        "date": now.strftime("%Y-%m-%d"),
        "weekday": "一二三四五六日"[now.weekday()],
        "time": now.strftime("%H:%M"),
        "timezone": "Asia/Taipei",
        "current_dm_period": f"{_DM_START} ~ {_DM_END}",
        "dm_days_remaining": max(0, days_left),
    }


@mcp.tool()
def get_store_hours(store_name: str) -> dict:
    """查詢指定分店的營業時間。

    Args:
        store_name: 分店名稱，例如「重新」「內湖」「屏東」（不含「店」字）
    """
    key = (store_name or "").strip().replace("店", "")
    hours = _STORE_HOURS.get(key)
    if hours is None:
        return {
            "found": False,
            "message": f"查無「{store_name}」的營業時間資料",
            "available_stores": sorted(_STORE_HOURS),
        }
    return {"found": True, "store": key, "hours": hours, "note": "國定假日營業時間以現場公告為準"}


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """查詢單筆訂單的狀態與金額明細。

    使用者詢問自己的訂單、帳單金額、退款進度時使用。需要訂單編號；
    使用者沒有提供編號時，請先向使用者詢問，不要自行猜測編號。

    Args:
        order_id: 訂單編號，格式如 A20260901007
    """
    oid = (order_id or "").strip().upper()
    order = _ORDERS.get(oid)
    if order is None:
        return {"found": False, "order_id": oid, "message": "查無此訂單編號，請確認後再試"}
    return {"found": True, "order_id": oid, **order}


def build_app():
    """把 FastMCP 的 streamable-http ASGI app 掛在含密鑰的路徑下。"""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    token = os.environ.get("MCP_PATH_TOKEN", "").strip()
    if not token:
        raise SystemExit("必須設定 MCP_PATH_TOKEN（網址路徑密鑰）")

    async def health(_request):
        return JSONResponse({"status": "ok", "tools": ["get_today", "get_store_hours", "get_order_status"]})

    return Starlette(routes=[
        Route("/health", health),
        Mount(f"/{token}", app=mcp.streamable_http_app()),
    ])


app = build_app() if os.environ.get("MCP_PATH_TOKEN") else None

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(build_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
