"""由程式產出 OpenAPI 並寫入 docs/api/openapi.json（Issue #97，準則 E1）。

用法：`make openapi`（在 apps/backend 執行 export_openapi.py）。
unit test `api_contract_batch1.feature` 會比對提交版本與程式產出，不一致即失敗。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT.parents[1] / "docs" / "api" / "openapi.json"


def main() -> int:
    # 與 unit test 的 api_app fixture 相同環境，確保產出一致
    os.environ.setdefault("E2E_MODE", "true")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake")
    sys.path.insert(0, str(ROOT))
    from src.main import create_app

    spec = create_app(skip_rate_limit=True).openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    ops = sum(
        1 for item in spec["paths"].values()
        for m in item if m in ("get", "post", "put", "patch", "delete")
    )
    print(f"wrote {OUT} — paths={len(spec['paths'])} operations={ops}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
