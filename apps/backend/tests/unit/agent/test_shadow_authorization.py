"""Regression: 影子執行授權閘（H19，review 標為零測試覆蓋）。

config_override / test_mode / history_override 允許以任意 prompt 走完整管線，唯一防線
是 _require_shadow_authorized（body 想影子執行但 usage 標記未通過 admin 授權 → 403）
與 resolve_usage_context（role 白名單）。
"""

import pytest
from fastapi import HTTPException

from src.application.usage.usage_context import (
    UsageContext,
    resolve_usage_context,
)
from src.interfaces.api.agent_router import (
    ChatRequest,
    _require_shadow_authorized,
)


def _req(**kw):
    return ChatRequest(message="hi", **kw)


# --- _require_shadow_authorized ---

@pytest.mark.parametrize("shadow_kw", [
    {"test_mode": True},
    {"config_override": {"base_prompt": "x"}},
    {"history_override": [{"role": "user", "content": "x"}]},
])
def test_shadow_without_eval_marker_forbidden(shadow_kw):
    with pytest.raises(HTTPException) as exc:
        _require_shadow_authorized(_req(**shadow_kw), UsageContext())  # chat_web
    assert exc.value.status_code == 403


@pytest.mark.parametrize("shadow_kw", [
    {"test_mode": True},
    {"config_override": {"base_prompt": "x"}},
])
def test_shadow_with_eval_marker_allowed(shadow_kw):
    ctx = UsageContext(request_type="eval_gate")
    _require_shadow_authorized(_req(**shadow_kw), ctx)  # no raise


def test_non_shadow_request_allowed():
    _require_shadow_authorized(_req(), UsageContext())  # no raise


# --- resolve_usage_context（role 白名單）---

def test_non_admin_eval_category_falls_back_to_chat_web():
    """非 admin 帶 eval 分類 → fallback chat_web（之後在 router 觸發 403）。"""
    ctx = resolve_usage_context("eval_gate", run_id="r1", role="user")
    assert ctx.request_type != "eval_gate"  # fallback
    # 且此 fallback 會讓影子請求被 _require_shadow_authorized 擋下
    with pytest.raises(HTTPException):
        _require_shadow_authorized(_req(test_mode=True), ctx)


def test_admin_eval_category_accepted():
    ctx = resolve_usage_context("eval_gate", run_id="r1", role="tenant_admin")
    assert ctx.request_type == "eval_gate"
    assert ctx.run_id == "r1"


def test_system_admin_eval_category_accepted():
    ctx = resolve_usage_context("prompt_optimize", run_id=None, role="system_admin")
    assert ctx.request_type == "prompt_optimize"
