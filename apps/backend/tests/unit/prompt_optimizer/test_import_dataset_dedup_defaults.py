"""Regression: import_dataset 寫入 case 斷言時剔除 defaults（M35）。

YAML 載入時 _parse_cases 已把 default_assertions 併進每個 case。若 import 原樣寫入，
read_dataset 讀回時又疊一次 default → 每個 default 斷言跑兩次、分數灌水、優化迴圈的
accept/discard 判斷失真。import 寫入前須剔除 defaults。
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

from prompt_optimizer.dataset import (
    Assertion,
    CostConfigData,
    Dataset,
    DatasetMetadata,
    TestCase,
)
from prompt_optimizer.db_client import PromptDBClient


def test_import_strips_default_assertions_from_case(monkeypatch):
    default_a = Assertion(type="not_empty", params={})
    default_b = Assertion(type="max_length", params={"n": 500})
    case_only = Assertion(type="contains", params={"text": "退貨"})

    dataset = Dataset(
        metadata=DatasetMetadata(
            tenant_id="t1", bot_id="b1", target_prompt="base_prompt",
            agent_mode="react", cost_config=CostConfigData(),
        ),
        default_assertions=(default_a, default_b),
        test_cases=(
            # _parse_cases 已把 defaults 併進 case → 這裡模擬「已含 defaults」
            TestCase(
                id="c1", question="q", priority="P1",
                assertions=(default_a, default_b, case_only),
            ),
        ),
    )

    captured: list = []

    class _FakeSession:
        def execute(self, _sql, params=None):
            if params is not None:
                captured.append(params)

        def commit(self):
            pass

    @contextmanager
    def _fake_session_ctx(_engine):
        yield _FakeSession()

    monkeypatch.setattr(
        "prompt_optimizer.db_client.Session", _fake_session_ctx
    )

    client = PromptDBClient.__new__(PromptDBClient)
    client._engine = MagicMock()
    client.import_dataset(dataset)

    # 找到 test-case INSERT 的 params（含 case_id）
    case_params = [p for p in captured if p.get("case_id") == "c1"]
    assert len(case_params) == 1
    stored = json.loads(case_params[0]["assertions"])
    types = {a["type"] for a in stored}
    # 只留 case 專屬斷言，兩個 default 被剔除
    assert types == {"contains"}
