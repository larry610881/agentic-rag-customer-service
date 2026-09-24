"""Regression（#469965）：eval_datasets.agent_mode 移除後 prompt_optimizer CLI 仍可用。

ORM 早已移除該欄（ce97472 / 558be1f），但 db_client 的 raw SQL 仍寫入
（import_dataset 的 INSERT 列出 agent_mode）並讀取（read_dataset 取
ds["agent_mode"]）。DROP COLUMN 之後前者 UndefinedColumn、後者 KeyError。
agent_mode 不影響任何評測行為，讀回時用 DatasetMetadata 預設值（= 原欄位的
DB 預設 'router'）。
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

from prompt_optimizer.dataset import CostConfigData, Dataset, DatasetMetadata
from prompt_optimizer.db_client import PromptDBClient


def _client(monkeypatch, session):
    @contextmanager
    def _ctx(_engine):
        yield session

    monkeypatch.setattr("prompt_optimizer.db_client.Session", _ctx)
    client = PromptDBClient.__new__(PromptDBClient)
    client._engine = MagicMock()
    return client


def test_import_不寫入_agent_mode(monkeypatch):
    sqls: list[str] = []
    params: list[dict] = []

    class _S:
        def execute(self, sql, p=None):
            sqls.append(str(sql))
            params.append(p or {})

        def commit(self):
            pass

    dataset = Dataset(
        metadata=DatasetMetadata(
            tenant_id="t1", target_prompt="bot_prompt", cost_config=CostConfigData()
        ),
        default_assertions=(),
        test_cases=(),
    )
    _client(monkeypatch, _S()).import_dataset(dataset)

    ds_insert = [s for s in sqls if "INSERT INTO eval_datasets" in s]
    assert len(ds_insert) == 1
    assert "agent_mode" not in ds_insert[0]
    assert all("agent_mode" not in p for p in params)


def test_read_dataset_在沒有_agent_mode_欄位時可讀回(monkeypatch):
    row = {
        "tenant_id": "t1",
        "bot_id": None,
        "target_prompt": "bot_prompt",
        "description": "d",
        "cost_config": {},
        "default_assertions": [],
    }

    class _S:
        def execute(self, sql, p=None):
            if "FROM eval_datasets" in str(sql):
                return SimpleNamespace(
                    fetchone=lambda: SimpleNamespace(_mapping=row)
                )
            return SimpleNamespace(fetchall=lambda: [])

    ds = _client(monkeypatch, _S()).read_dataset("ds-1")
    assert ds.metadata.tenant_id == "t1"
    assert ds.metadata.agent_mode == "router"
