"""Regression（Issue #60 上線 bug）：新 router 沒登記進 Container.wiring_config

症狀：/api/v1/audit-logs 回 500 `'Provide' object has no attribute 'execute'`——
router 用 `Depends(Provide[Container.x])` 但模組不在 wiring 清單，DI 不會替換。
守門：所有 src/interfaces/api/*_router.py 只要用到 Provide[ 就必須在 wiring 清單裡。
"""

import re
from pathlib import Path

from src.container import Container

API_DIR = Path(__file__).resolve().parents[3] / "src" / "interfaces" / "api"


def _router_modules_using_provide() -> set[str]:
    modules: set[str] = set()
    for path in API_DIR.glob("*_router.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"Provide\[", text):
            modules.add(f"src.interfaces.api.{path.stem}")
    return modules


def test_every_router_using_provide_is_wired():
    wired = set(Container.wiring_config.modules)
    missing = sorted(_router_modules_using_provide() - wired)
    assert missing == [], f"routers not in Container.wiring_config: {missing}"


def test_issue60_routers_are_wired():
    wired = set(Container.wiring_config.modules)
    assert "src.interfaces.api.audit_log_router" in wired
    assert "src.interfaces.api.config_snapshot_router" in wired
