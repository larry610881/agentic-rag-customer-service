"""Regression: guard 細節暴露以 JWT role 判定，非 body identity_source（M13）。"""

from src.interfaces.api.agent_router import (
    _can_see_guard_details,
    _maybe_expose_guard,
)


def test_non_admin_cannot_see_guard_details():
    assert _can_see_guard_details("user") is False
    assert _can_see_guard_details(None) is False
    # 即使 result 有 guard 資訊，非 admin 也拿到 (None, None)
    assert _maybe_expose_guard("input", "SECRET_REGEX", "user") == (None, None)


def test_admin_roles_see_guard_details():
    assert _can_see_guard_details("system_admin") is True
    assert _can_see_guard_details("tenant_admin") is True
    assert _maybe_expose_guard("input", "SECRET_REGEX", "system_admin") == (
        "input",
        "SECRET_REGEX",
    )


def test_test_back_backdoor_removed():
    """M11：生產不得殘留 test-back 錯誤模擬觸發器（任何登入者可偽造錯誤事件）。"""
    from pathlib import Path

    src = Path("src/interfaces/api/agent_router.py").read_text(encoding="utf-8")
    assert "test-back" not in src
    assert "TEST TRIGGER" not in src
