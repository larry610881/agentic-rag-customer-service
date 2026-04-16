"""TransferToHumanTool behaviour tests."""
from __future__ import annotations

import asyncio

from src.infrastructure.langgraph.transfer_to_human_tool import (
    TransferToHumanTool,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_returns_success_contact_when_url_configured():
    tool = TransferToHumanTool()
    result = _run(
        tool.invoke(
            customer_service_url="https://example.com/support",
            reason="退款爭議",
        )
    )
    assert result["success"] is True
    assert result["contact"] is not None
    assert result["contact"]["url"] == "https://example.com/support"
    assert result["contact"]["type"] == "url"
    assert result["contact"]["label"]  # non-empty
    assert "退款爭議" in result["context"]


def test_falls_back_when_url_missing():
    tool = TransferToHumanTool()
    result = _run(tool.invoke(customer_service_url="", reason=""))
    assert result["success"] is False
    assert result["contact"] is None
    assert "未設定" in result["context"]


def test_reason_optional():
    tool = TransferToHumanTool()
    result = _run(
        tool.invoke(customer_service_url="https://ex.com", reason="")
    )
    assert result["success"] is True
    # 無 reason 時 context 不應出現 "（原因：" 片段
    assert "（原因：" not in result["context"]


def test_custom_label_propagates():
    tool = TransferToHumanTool(default_label="立即聯絡專員")
    result = _run(
        tool.invoke(customer_service_url="https://ex.com")
    )
    assert result["contact"]["label"] == "立即聯絡專員"
