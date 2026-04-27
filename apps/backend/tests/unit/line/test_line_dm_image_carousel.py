"""Regression test — LINE handler 處理 DM 圖卡 (image_url 保留 + Source dataclass 支援)

Bug history (2026-04-27):
家樂福 LINE bot 切到 anthropic claude-haiku-4-5 後，DM 子頁 PNG carousel
不再顯示，且對話歷史的 retrieved_chunks 只剩 3 個欄位（image_url 不見）。

Two root causes in apps/backend/src/application/line/handle_webhook_use_case.py:

1. retrieved_chunks 寫入時手動只挑 3 個欄位（document_name/content_snippet/score），
   把 dm tool 的 image_url + page_number + chunk_id + ... 全砍掉
   → web/Studio 跨 channel 重看 LINE 對話拿不到圖卡。

2. image_sources filter 只接受 isinstance(s, dict)，但
   react_agent_service.process_message 已把 dm_tool dict 重建為 Source
   dataclass → image_sources 永遠空 → Flex carousel 永遠不發送。

此測試守住「image_url 不被丟」+「Source dataclass 也能進 carousel」。
"""
from src.domain.rag.value_objects import Source


def test_source_dataclass_has_image_url_field():
    """Source dataclass 必須能裝 image_url + page_number"""
    s = Source(
        document_name="第 9 頁 — DM",
        content_snippet="snippet",
        score=0.5,
        chunk_id="c1",
        image_url="https://gcs/page-9.png",
        page_number=9,
    )
    assert s.image_url == "https://gcs/page-9.png"
    assert s.page_number == 9


def test_image_sources_filter_supports_dataclass():
    """模擬 LINE handler line 530-545 的 filter 邏輯：
    Source dataclass + dict 兩種都應被認出有 image_url。"""
    sources = [
        Source(
            document_name="第 9 頁",
            content_snippet="...",
            score=0.5,
            chunk_id="c1",
            image_url="https://gcs/page-9.png",
            page_number=9,
        ),
        {  # dict 路徑（mcp tool 直接透傳的情況）
            "document_name": "第 47 頁",
            "content_snippet": "...",
            "score": 0.4,
            "image_url": "https://gcs/page-47.png",
            "page_number": 47,
        },
        Source(  # 沒有 image_url 的 rag_query 來源 — 不該進 carousel
            document_name="退貨政策",
            content_snippet="...",
            score=0.3,
            chunk_id="c2",
        ),
    ]

    image_sources: list[dict] = []
    for s in sources:
        if isinstance(s, dict):
            url = s.get("image_url", "")
            payload = s
        else:
            url = getattr(s, "image_url", "") or ""
            payload = s.to_dict() if hasattr(s, "to_dict") else None
        if url and payload is not None:
            image_sources.append(payload)

    assert len(image_sources) == 2
    urls = [s["image_url"] for s in image_sources]
    assert "https://gcs/page-9.png" in urls
    assert "https://gcs/page-47.png" in urls


def test_retrieved_chunks_persist_full_dict_via_to_dict():
    """模擬 LINE handler 寫入 retrieved_chunks 的 list comprehension：
    Source dataclass.to_dict() 必須帶 image_url + page_number。"""
    sources = [
        Source(
            document_name="第 9 頁 — DM",
            content_snippet="snippet 9",
            score=0.555,
            chunk_id="c1",
            document_id="d1",
            kb_id="kb1",
            image_url="https://gcs/page-9.png",
            page_number=9,
        )
    ]
    chunks = [
        s if isinstance(s, dict) else s.to_dict()
        for s in sources
    ]
    assert chunks[0]["image_url"] == "https://gcs/page-9.png"
    assert chunks[0]["page_number"] == 9
    assert chunks[0]["document_name"] == "第 9 頁 — DM"
    assert chunks[0]["chunk_id"] == "c1"
