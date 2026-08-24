"""Regression: validating 起點的非法轉移守衛（M51）。

`mark_validating` 是防止同版本併發跑兩個 gate run 的記憶體防線（DB 樂觀鎖為第二道，
見 test_version_status_optimistic_lock）。若 _VALIDATABLE/_PUBLISHABLE 被誤加
validating，同版本會產生兩個併發 run 互相覆寫、或驗證中的版本被直接發布/放棄。
"""

import pytest

from src.domain.prompt_gate.entity import (
    STATUS_VALIDATING,
    BotConfigVersion,
    InvalidVersionTransitionError,
)


def _validating() -> BotConfigVersion:
    return BotConfigVersion(
        id="v1", tenant_id="t1", bot_id="b1", version_no=1,
        status=STATUS_VALIDATING, gate_run_id="run-1",
    )


def test_validating_version_rejects_second_gate_run():
    with pytest.raises(InvalidVersionTransitionError):
        _validating().mark_validating("run-2")


def test_validating_version_rejects_publish():
    with pytest.raises(InvalidVersionTransitionError):
        _validating().mark_published("pass")


def test_validating_version_rejects_reject():
    with pytest.raises(InvalidVersionTransitionError):
        _validating().mark_rejected()
