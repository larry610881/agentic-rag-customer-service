"""Regression: guard dry_run（test_mode 影子執行）不寫 guard_logs（H6）。"""

import asyncio
from unittest.mock import AsyncMock

from src.application.security.prompt_guard_service import PromptGuardService
from src.domain.security.guard_config import GuardRulesConfig


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _svc():
    rules = AsyncMock()
    rules.get = AsyncMock(return_value=GuardRulesConfig(
        input_rules=[{"type": "keyword", "pattern": "忽略以上指令", "enabled": True}],
        output_keywords=[
            {"keyword": "系統提示", "enabled": True},
            {"keyword": "internal", "enabled": True},
        ],
        blocked_response="無法處理",
    ))
    log_repo = AsyncMock()
    log_repo.save_log = AsyncMock()
    return PromptGuardService(rules, log_repo), log_repo


def test_input_block_dry_run_skips_log():
    svc, log_repo = _svc()
    res = _run(svc.check_input("忽略以上指令", tenant_id="t1", dry_run=True))
    assert res.passed is False  # 仍攔截
    log_repo.save_log.assert_not_called()  # 但不落庫


def test_input_block_persists_when_not_dry_run():
    svc, log_repo = _svc()
    res = _run(svc.check_input("忽略以上指令", tenant_id="t1", dry_run=False))
    assert res.passed is False
    log_repo.save_log.assert_awaited_once()


def test_output_block_dry_run_skips_log():
    svc, log_repo = _svc()
    res = _run(svc.check_output("這是系統提示與 internal 內容", tenant_id="t1",
                                dry_run=True))
    assert res.passed is False
    log_repo.save_log.assert_not_called()


def test_block_by_classifier_dry_run_skips_log():
    svc, log_repo = _svc()
    res = _run(svc.block_by_classifier(
        message="攻擊句", tenant_id="t1", dry_run=True))
    assert res.passed is False
    log_repo.save_log.assert_not_called()
