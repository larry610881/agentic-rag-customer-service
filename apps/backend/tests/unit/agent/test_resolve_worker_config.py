"""Regression test: WorkerConfig.worker_prompt 必須正確轉為 cfg['system_prompt']。

Bug 背景（2026-04-16）：
    commit f39a165 將 WorkerConfig.system_prompt rename 為 worker_prompt，
    但 SendMessageUseCase._resolve_worker_config 漏改了兩處存取，
    導致 supervisor/worker 模式的 bot 在 chat 時拋 AttributeError:
        'WorkerConfig' object has no attribute 'system_prompt'
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.agent.send_message_use_case import SendMessageUseCase
from src.domain.bot.worker_config import WorkerConfig


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _build_use_case(workers, matched_worker):
    """Build a SendMessageUseCase with minimal mocked deps to exercise
    _resolve_worker_config only.
    """
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=workers)

    intent_classifier = AsyncMock()
    intent_classifier.classify_workers = AsyncMock(return_value=matched_worker)

    uc = SendMessageUseCase.__new__(SendMessageUseCase)
    uc._worker_config_repo = worker_repo
    uc._intent_classifier = intent_classifier
    return uc


def test_resolve_worker_config_uses_worker_prompt_not_system_prompt():
    """Regression: matched worker 的 worker_prompt 必須寫入 cfg['system_prompt']。

    以前 code 用 matched.system_prompt 會炸 AttributeError；
    rename 後正確欄位是 worker_prompt。
    """
    worker = WorkerConfig(
        bot_id="bot-001",
        name="客訴處理",
        description="處理客訴",
        worker_prompt="你是客訴專員，請耐心傾聽。",
        max_tool_calls=3,
    )
    uc = _build_use_case(workers=[worker], matched_worker=worker)

    bot_cfg = {
        "bot_id": "bot-001",
        "system_prompt": "你是通用客服。",
    }

    result = _run(
        uc._resolve_worker_config(
            bot_cfg=bot_cfg,
            message="我要投訴",
            router_context="",
        )
    )

    # worker_prompt 必須覆寫 bot 層的 system_prompt
    assert "你是客訴專員" in result["system_prompt"]
    assert result["max_tool_calls"] == 3


def test_resolve_worker_config_keeps_bot_prompt_when_worker_prompt_empty():
    """Regression: worker_prompt 空字串時不應覆寫 bot 的 system_prompt。"""
    worker = WorkerConfig(
        bot_id="bot-001",
        name="預設",
        worker_prompt="",  # 空字串 — 不覆寫
    )
    uc = _build_use_case(workers=[worker], matched_worker=worker)

    bot_cfg = {
        "bot_id": "bot-001",
        "system_prompt": "你是通用客服。",
    }

    result = _run(
        uc._resolve_worker_config(
            bot_cfg=bot_cfg,
            message="hi",
            router_context="",
        )
    )

    assert result["system_prompt"] == "你是通用客服。"
