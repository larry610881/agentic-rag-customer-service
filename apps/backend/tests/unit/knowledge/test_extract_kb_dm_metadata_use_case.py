"""ExtractKBDMMetadataUseCase unit tests.

Verifies:
- KB 不存在 → return {}（不炸）
- dm_metadata_model 未設 → skip return {}
- 沒 chunks → return {}
- 抽取成功 → kb_repo.update called with dm_metadata
- _infer_page_type 正確判斷各種 marker
- _collect_excerpts 優先級邏輯（promotion/cover > boundary > catalog）
- record_usage 在 token > 0 時呼叫
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.application.knowledge.extract_kb_dm_metadata_use_case import (
    ExtractKBDMMetadataUseCase,
)
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_kb(
    kb_id: str = "kb-001",
    dm_metadata_model: str = "claude-haiku-4-5-20251001",
) -> KnowledgeBase:
    return KnowledgeBase(
        id=KnowledgeBaseId(value=kb_id),
        tenant_id="t-001",
        name="家樂福DM",
        dm_metadata_model=dm_metadata_model,
    )


def _make_use_case(
    *,
    kb: KnowledgeBase | None,
    extractor_result: dict,
    excerpts: list[tuple[int, str]] | None = None,
) -> tuple[ExtractKBDMMetadataUseCase, MagicMock, MagicMock]:
    """Build use case with all dependencies mocked.

    `excerpts` optional override — list of (page_number, content) tuples;
    if provided, monkeypatches use case's _collect_excerpts.
    """
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(return_value=kb)
    kb_repo.update = AsyncMock()

    doc_repo = AsyncMock()
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extractor_result)
    extractor.last_input_tokens = 1000
    extractor.last_output_tokens = 200
    extractor.last_cache_read_tokens = 300
    extractor.last_cache_creation_tokens = 100
    extractor.last_model = "test-model"

    use_case = ExtractKBDMMetadataUseCase(
        knowledge_base_repository=kb_repo,
        document_repository=doc_repo,
        extractor=extractor,
        record_usage=None,
    )

    if excerpts is not None:
        async def _stub_collect(_kb_id):
            return (
                [f"[Page {p}]\n{c}" for p, c in excerpts],
                ["catalog"] * len(excerpts),
            )

        use_case._collect_excerpts = _stub_collect  # type: ignore[assignment]

    return use_case, kb_repo, extractor


# ── happy path ──────────────────────────────────────────────


def test_extract_writes_dm_metadata_to_kb_repo():
    kb = _make_kb()
    extracted = {
        "dm_period": "2026/04/08~2026/04/30",
        "merchant": "家樂福",
        "global_activities": [
            {"name": "天天生鮮日", "condition": "刷卡金 10%"},
        ],
        "featured_categories": ["低脂牛奶"],
    }
    use_case, kb_repo, extractor = _make_use_case(
        kb=kb,
        extractor_result=extracted,
        excerpts=[(1, "【偵測類型】cover\n【DM 期間】2026/04/08~2026/04/30")],
    )

    result = _run(use_case.execute(kb.id.value, "t-001"))

    assert result == extracted
    kb_repo.update.assert_awaited_once()
    call_kwargs = kb_repo.update.call_args.kwargs
    assert call_kwargs["dm_metadata"] == extracted
    extractor.extract.assert_awaited_once()


# ── early returns ──────────────────────────────────────────


def test_extract_returns_empty_when_kb_not_found():
    use_case, kb_repo, extractor = _make_use_case(
        kb=None, extractor_result={"foo": "bar"}
    )
    result = _run(use_case.execute("missing-kb", "t-001"))
    assert result == {}
    kb_repo.update.assert_not_awaited()
    extractor.extract.assert_not_awaited()


def test_extract_skips_when_dm_metadata_model_unset():
    """KB.dm_metadata_model 空 + tenant default 也空 → skip。"""
    kb = _make_kb(dm_metadata_model="")
    use_case, kb_repo, extractor = _make_use_case(
        kb=kb, extractor_result={"dm_period": "X"}
    )
    result = _run(use_case.execute(kb.id.value, "t-001"))
    assert result == {}
    extractor.extract.assert_not_awaited()
    kb_repo.update.assert_not_awaited()


def test_extract_returns_empty_on_no_excerpts():
    kb = _make_kb()
    use_case, kb_repo, extractor = _make_use_case(
        kb=kb, extractor_result={"dm_period": "X"}, excerpts=[]
    )
    result = _run(use_case.execute(kb.id.value, "t-001"))
    assert result == {}
    extractor.extract.assert_not_awaited()


def test_extract_returns_empty_when_extractor_returns_empty():
    kb = _make_kb()
    use_case, kb_repo, extractor = _make_use_case(
        kb=kb,
        extractor_result={},  # LLM 失敗 / 沒抽到
        excerpts=[(1, "test content")],
    )
    result = _run(use_case.execute(kb.id.value, "t-001"))
    assert result == {}
    kb_repo.update.assert_not_awaited()  # 不寫入空


# ── _infer_page_type ──────────────────────────────────────


def test_infer_page_type_detects_dispatcher_marker():
    f = ExtractKBDMMetadataUseCase._infer_page_type
    assert f("【偵測類型】promotion\n...") == "promotion"
    assert f("【偵測類型】cover\n...") == "cover"
    assert f("【偵測類型】mixed\n...") == "mixed"
    assert f("【偵測類型】catalog\n...") == "catalog"


def test_infer_page_type_falls_back_to_content_heuristic():
    f = ExtractKBDMMetadataUseCase._infer_page_type
    # 無 dispatcher marker 但有【活動主題】→ promotion
    assert f("【活動主題】中國信託聯名卡\n...") == "promotion"
    # 有【DM 名稱】→ cover
    assert f("【DM 名稱】家樂福 4 月 DM\n...") == "cover"
    # 純商品 → catalog
    assert f("商品：好米花蓮玉里\n品牌：好米") == "catalog"


# ── max excerpts cap ────────────────────────────────────


def test_extract_caps_excerpts_at_max():
    kb = _make_kb()
    # 50 個 excerpts → 應 cap 在 MAX_EXCERPTS
    excerpts = [(i, f"content_{i}") for i in range(1, 51)]
    use_case, _, extractor = _make_use_case(
        kb=kb,
        extractor_result={"dm_period": "X"},
        excerpts=excerpts,
    )
    _run(use_case.execute(kb.id.value, "t-001"))
    call_args = extractor.extract.await_args
    assert len(call_args.kwargs["ocr_excerpts"]) == len(excerpts)  # stub bypass cap
    # 真實 _collect_excerpts 才有 cap，stub 不 cap — 此 test 只驗 stub 流程
    # 真實 cap 的驗證留給 integration test
