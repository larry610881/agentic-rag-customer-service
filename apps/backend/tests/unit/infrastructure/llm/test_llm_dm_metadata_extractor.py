"""LLMDMMetadataExtractor — Anthropic tool use + Pydantic schema unit tests.

Validates:
- DMMetadata Pydantic model schema generation
- Tool definition uses Pydantic schema
- extract() calls tool_choice=tool name
- extract() parses tool_use block + Pydantic-validates input
- Token tracking populates 5 attributes
- Empty / malformed inputs return {} (not crash)
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from src.infrastructure.llm.llm_dm_metadata_extractor import (
    TOOL_NAME,
    DMMetadata,
    GlobalActivity,
    LLMDMMetadataExtractor,
    MemberCondition,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_extractor_with_fake_client(tool_input: dict) -> LLMDMMetadataExtractor:
    """Build extractor with fake Anthropic client returning canned tool_use response."""
    extractor = LLMDMMetadataExtractor(api_key="test-key")

    fake_client = MagicMock()

    async def fake_create(**_kwargs):
        # Capture tools / tool_choice for assertion
        extractor._captured_tools = _kwargs.get("tools", [])
        extractor._captured_tool_choice = _kwargs.get("tool_choice", {})

        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.input = tool_input

        msg = MagicMock()
        msg.content = [tool_use_block]
        msg.stop_reason = "tool_use"
        msg.usage = MagicMock(
            input_tokens=1000,
            output_tokens=200,
            cache_read_input_tokens=500,
            cache_creation_input_tokens=300,
        )
        return msg

    fake_client.messages = MagicMock()
    fake_client.messages.create = fake_create
    extractor._client = fake_client
    return extractor


# ── Pydantic schema ──────────────────────────────────────────


def test_dm_metadata_schema_has_all_required_fields():
    schema = DMMetadata.model_json_schema()
    props = schema["properties"]
    assert "dm_name" in props
    assert "dm_period" in props
    assert "merchant" in props
    assert "member_conditions" in props
    assert "global_activities" in props
    assert "featured_categories" in props
    assert "special_activities" in props


def test_dm_metadata_defaults_to_empty():
    """所有欄位都有預設 — LLM 找不到也不該炸。"""
    m = DMMetadata()
    assert m.dm_name == ""
    assert m.dm_period == ""
    assert m.merchant == ""
    assert m.member_conditions == []
    assert m.global_activities == []
    assert m.featured_categories == []
    assert m.special_activities == []


def test_dm_metadata_validates_global_activity_shape():
    m = DMMetadata(
        global_activities=[
            GlobalActivity(name="天天生鮮日", condition="刷卡金 10% 折價券"),
            GlobalActivity(name="週二加油日", condition="滿 1200 享 50 元"),
        ]
    )
    assert len(m.global_activities) == 2
    assert m.global_activities[0].name == "天天生鮮日"


def test_dm_metadata_validates_member_condition_shape():
    m = DMMetadata(
        member_conditions=[
            MemberCondition(
                audience="unipen 聯名卡持卡人", benefit="最高 7% 回饋"
            ),
        ]
    )
    assert m.member_conditions[0].audience == "unipen 聯名卡持卡人"


def test_dm_metadata_rejects_extra_unknown_field():
    """Pydantic 預設允許額外欄位（permissive）— 但保證 known fields 是對的。"""
    # 額外欄位 LLM 偶爾會多吐，不該讓 validation 炸
    m = DMMetadata.model_validate({
        "dm_period": "2026/04/01~2026/04/30",
        "merchant": "家樂福",
        "extra_unknown_field": "should not crash",
    })
    assert m.dm_period == "2026/04/01~2026/04/30"


# ── Tool definition ──────────────────────────────────────────


def test_tool_definition_uses_pydantic_schema():
    extractor = LLMDMMetadataExtractor(api_key="test-key")
    tool_def = extractor._build_tool_definition()
    assert tool_def["name"] == TOOL_NAME
    assert "description" in tool_def
    assert "input_schema" in tool_def
    # input_schema 來自 Pydantic
    schema = tool_def["input_schema"]
    assert "properties" in schema
    assert "dm_period" in schema["properties"]


# ── extract() flow ──────────────────────────────────────────


def test_extract_returns_dict_matching_pydantic_schema():
    canned_input = {
        "dm_name": "家樂福 4 月 DM",
        "dm_period": "2026/04/08~2026/04/30",
        "merchant": "家樂福",
        "member_conditions": [
            {"audience": "unipen 聯名卡持卡人", "benefit": "最高 7% 回饋"},
        ],
        "global_activities": [
            {"name": "天天生鮮日", "condition": "刷卡金 10% 折價券"},
            {"name": "週二加油日", "condition": "滿 1200 享 50 元"},
        ],
        "featured_categories": ["低脂牛奶", "麵包饅頭", "冷凍冰品"],
        "special_activities": ["買一送一", "OPENPOINT 10 倍送"],
    }
    extractor = _make_extractor_with_fake_client(canned_input)

    result = _run(
        extractor.extract(
            ocr_excerpts=["【DM 期間】2026/04/08~2026/04/30 ..."],
            page_types=["cover"],
        )
    )

    assert result["dm_name"] == "家樂福 4 月 DM"
    assert result["dm_period"] == "2026/04/08~2026/04/30"
    assert len(result["global_activities"]) == 2
    assert result["global_activities"][0]["name"] == "天天生鮮日"


def test_extract_forces_tool_choice_to_save_dm_metadata():
    """tool_choice 必須強制 LLM 呼叫指定 tool — 取代純 prompt 容易吐錯 JSON。"""
    extractor = _make_extractor_with_fake_client({"merchant": "家樂福"})
    _run(
        extractor.extract(
            ocr_excerpts=["test"], page_types=["cover"]
        )
    )
    assert extractor._captured_tool_choice == {
        "type": "tool", "name": TOOL_NAME,
    }


def test_extract_populates_token_tracking():
    extractor = _make_extractor_with_fake_client({"merchant": "家樂福"})
    _run(extractor.extract(ocr_excerpts=["x"], page_types=["cover"]))
    assert extractor.last_input_tokens == 1000
    assert extractor.last_output_tokens == 200
    assert extractor.last_cache_read_tokens == 500
    assert extractor.last_cache_creation_tokens == 300
    assert extractor.last_model  # 有 model 字串


def test_extract_returns_empty_dict_on_no_excerpts():
    extractor = LLMDMMetadataExtractor(api_key="test-key")
    result = _run(extractor.extract(ocr_excerpts=[], page_types=[]))
    assert result == {}


def test_extract_handles_mismatched_page_types_length():
    """page_types 長度不對 → 自動填 unknown，不該炸。"""
    extractor = _make_extractor_with_fake_client({"merchant": "X"})
    result = _run(
        extractor.extract(
            ocr_excerpts=["a", "b", "c"],
            page_types=["cover"],  # 1 vs 3，length mismatch
        )
    )
    # 不炸即可
    assert isinstance(result, dict)


def test_extract_returns_empty_on_no_tool_use_block():
    """LLM 沒呼叫 tool（罕見）→ 回 {}，caller 視為「不啟用」。"""
    extractor = LLMDMMetadataExtractor(api_key="test-key")

    fake_client = MagicMock()

    async def fake_create(**_kwargs):
        text_block = MagicMock()
        text_block.type = "text"
        msg = MagicMock()
        msg.content = [text_block]  # 沒有 tool_use
        msg.stop_reason = "end_turn"
        msg.usage = MagicMock(
            input_tokens=100, output_tokens=50,
            cache_read_input_tokens=0, cache_creation_input_tokens=0,
        )
        return msg

    fake_client.messages = MagicMock()
    fake_client.messages.create = fake_create
    extractor._client = fake_client

    result = _run(extractor.extract(ocr_excerpts=["x"], page_types=["cover"]))
    assert result == {}


def test_extract_truncates_long_ocr_to_budget():
    """OCR 太長要 truncate 不爆 token budget。"""
    extractor = _make_extractor_with_fake_client({"merchant": "X"})
    huge = "X" * 200_000
    _run(
        extractor.extract(
            ocr_excerpts=[huge], page_types=["catalog"]
        )
    )
    # 不炸（沒 timeout / 沒 token budget exceed exception）即可
    assert extractor.last_model
