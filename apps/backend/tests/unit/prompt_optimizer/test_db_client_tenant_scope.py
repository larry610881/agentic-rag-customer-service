"""Regression: PromptDBClient bot 層操作綁 tenant_id（M36）。"""

import pytest

from prompt_optimizer.config import PromptTarget
from prompt_optimizer.db_client import _TARGET_MAP, _build_params


def test_bot_targets_where_includes_tenant():
    for key in (("bot", "bot_prompt"), ("bot", "base_prompt")):
        _table, _col, where = _TARGET_MAP[key]
        assert "tenant_id = :tenant_id" in where


def test_bot_params_require_tenant_and_bot():
    p = _build_params(PromptTarget(
        level="bot", field="base_prompt", bot_id="b1", tenant_id="t1"))
    assert p == {"bot_id": "b1", "tenant_id": "t1"}


def test_bot_without_tenant_rejected():
    with pytest.raises(ValueError):
        _build_params(PromptTarget(
            level="bot", field="base_prompt", bot_id="b1", tenant_id=""))


def test_bot_without_bot_id_rejected():
    with pytest.raises(ValueError):
        _build_params(PromptTarget(
            level="bot", field="base_prompt", bot_id=None, tenant_id="t1"))


def test_system_level_needs_no_tenant():
    assert _build_params(PromptTarget(
        level="system", field="system_prompt")) == {}
