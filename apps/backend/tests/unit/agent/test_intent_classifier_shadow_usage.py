"""Regression: test_mode 影子執行的分類 token 不記成生產用量（M14）。

閘門 run / 優化迴圈以 test_mode=True 跑 N 個 case，每個 case 都會經
IntentClassifier 分類。#54 的 eval token 分流只涵蓋主模型（router 層 usage_ctx），
分類器這條原本無視 test_mode 直接 record_usage(request_type=INTENT_CLASSIFY) →
N 筆分類 token 記成生產用量並計入租戶帳務。影子執行必須略過生產記帳。
"""

import asyncio
from dataclasses import dataclass, field
from unittest.mock import AsyncMock

from src.application.agent.intent_classifier import IntentClassifier
from src.domain.bot.worker_config import WorkerConfig


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@dataclass
class FakeUsage:
    input_tokens: int = 20
    output_tokens: int = 10
    total_tokens: int = 30


@dataclass
class FakeLLMResult:
    text: str
    usage: FakeUsage = field(default_factory=FakeUsage)


def _make(record_usage):
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = FakeLLMResult(text="查詢\nOK")
    classifier = IntentClassifier(
        llm_service=mock_llm, record_usage=record_usage
    )
    return classifier


def _workers():
    return [
        WorkerConfig(id="w1", bot_id="b1", name="查詢", description="產品詢問"),
    ]


def test_production_mode_records_usage():
    record_usage = AsyncMock()
    classifier = _make(record_usage)
    _run(classifier.classify_sanitize(
        "退貨怎麼辦", "", _workers(), tenant_id="t1", bot_id="b1",
    ))
    record_usage.execute.assert_awaited_once()


def test_shadow_mode_skips_production_usage():
    record_usage = AsyncMock()
    classifier = _make(record_usage)
    _run(classifier.classify_sanitize(
        "退貨怎麼辦", "", _workers(), tenant_id="t1", bot_id="b1",
        test_mode=True,
    ))
    # 影子執行：分類 token 不得記成生產 intent_classify
    record_usage.execute.assert_not_called()
