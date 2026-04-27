"""Regression test — Source 欄位保留 image_url + page_number

Bug history (2026-04-27):
家樂福subagent測試 bot 切到 anthropic claude-haiku-4-5 後，DM 子頁圖卡
（query_dm_with_image 結果）不再顯示。Root cause:
- Source dataclass 沒有 image_url / page_number 欄位
- process_message 把 dm_tool 的 dict 重建成 Source 時，這兩個 key 被吞掉
- 前端 SourceImageGallery 找不到 image_url → 不渲染圖卡

此測試守住「Source.to_dict() 一定要有 image_url + page_number」+
「process_message 從 dict 重建 Source 時 image_url 不能丟」的合約。
"""
from src.domain.rag.value_objects import Source


def test_source_to_dict_includes_image_url_and_page_number():
    """新增的兩欄必須出現在 to_dict 輸出"""
    s = Source(
        document_name="第 9 頁 — DM",
        content_snippet="商品 X 特價",
        score=0.55,
        chunk_id="c1",
        document_id="d1",
        kb_id="kb1",
        image_url="https://gcs/signed/url",
        page_number=9,
    )
    d = s.to_dict()
    assert d["image_url"] == "https://gcs/signed/url"
    assert d["page_number"] == 9
    # 既有欄位仍須存在
    assert d["document_name"] == "第 9 頁 — DM"
    assert d["score"] == 0.55


def test_source_default_image_url_empty_for_rag_query():
    """rag_query 來源沒有圖卡 — image_url 預設空字串、page_number=0"""
    s = Source(
        document_name="退貨政策",
        content_snippet="商品可在 7 天內申請退貨",
        score=0.8,
        chunk_id="c1",
    )
    d = s.to_dict()
    assert d["image_url"] == ""
    assert d["page_number"] == 0


def test_source_round_trip_dict_keeps_image_url():
    """模擬 react_agent_service.process_message 的重建路徑：
    dm_tool dict → Source(...) → to_dict() 應保留 image_url"""
    dm_dict = {
        "document_id": "d1",
        "document_name": "第 47 頁 — 冬季冷凍食品促銷",
        "page_number": 47,
        "content_snippet": "杜老爺特級冰淇淋系列 $79元/瓶",
        "score": 0.537,
        "image_url": "https://gcs/signed/page-47.png",
    }
    s = Source(
        document_name=dm_dict.get("document_name", "rag_query"),
        content_snippet=dm_dict.get("content_snippet", ""),
        score=float(dm_dict.get("score", 0.0) or 0.0),
        chunk_id=dm_dict.get("chunk_id", ""),
        document_id=dm_dict.get("document_id", ""),
        kb_id=dm_dict.get("kb_id", ""),
        image_url=dm_dict.get("image_url", ""),
        page_number=int(dm_dict.get("page_number", 0) or 0),
    )
    out = s.to_dict()
    assert out["image_url"] == "https://gcs/signed/page-47.png"
    assert out["page_number"] == 47
    assert out["document_name"] == "第 47 頁 — 冬季冷凍食品促銷"
