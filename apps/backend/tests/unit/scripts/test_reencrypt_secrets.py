"""重新加密腳本（Issue #105）：dry-run、冪等、分批、單筆失敗繼續、巢狀 MCP env。"""

import asyncio
from typing import Any

from scripts.reencrypt_secrets import (
    ENCRYPTED_FIELDS,
    format_report,
    process_field,
)
from src.infrastructure.crypto.aes_encryption_service import AESEncryptionService
from tests.unit.repositories.spy_session import FakeResult, SpySession

K1 = "11" * 32
K2 = "22" * 32
OLD = AESEncryptionService(master_key=K1)  # 輪替前：v1、無前綴
NEW = AESEncryptionService(master_key=K2, key_id="v2", previous_keys=f"v1:{K1}")

PROVIDER = next(f for f in ENCRYPTED_FIELDS if f.name.startswith("provider_settings"))
NOTIFY = next(f for f in ENCRYPTED_FIELDS if f.name.startswith("notification"))
BOTS = next(f for f in ENCRYPTED_FIELDS if f.name.startswith("bots."))


def _is_select(stmt: Any) -> bool:
    return str(stmt).lstrip().upper().startswith("SELECT")


class SelectQueueSession(SpySession):
    """只有 SELECT 會取佇列裡的結果；UPDATE 回空結果（不消耗佇列）。"""

    def __init__(self, batches: list[list[Any]]) -> None:
        super().__init__()
        for rows in batches:
            self.queue_result(rows)

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> FakeResult:
        self.statements.append(stmt)
        if _is_select(stmt) and self._queued:
            return self._queued.popleft()
        return FakeResult()

    def updates(self) -> list[Any]:
        return [s for s in self.statements if not _is_select(s)]


def _run(session, spec, *, dry_run, batch_size=100, svc=NEW):
    return asyncio.run(
        process_field(session, svc, spec, dry_run=dry_run, batch_size=batch_size)
    )


def _written_value(stmt: Any, column: str) -> Any:
    return stmt.compile().params[column]


def test_dry_run_只統計不寫入():
    rows = [("p1", OLD.encrypt("k1")), ("p2", NEW.encrypt("k2")), ("p3", "")]
    session = SelectQueueSession([rows])
    report = _run(session, PROVIDER, dry_run=True)
    assert (report.scanned, report.stale, report.already_active) == (3, 1, 1)
    assert report.reencrypted == 0
    assert session.updates() == [] and session.commits == 0


def test_執行時以_active_金鑰重寫且可解回原文():
    rows = [("p1", OLD.encrypt("sk-live-1"))]
    session = SelectQueueSession([rows])
    report = _run(session, PROVIDER, dry_run=False)
    (stmt,) = session.updates()
    new_ct = _written_value(stmt, "api_key_encrypted")
    assert new_ct.startswith("v2:")
    assert NEW.decrypt(new_ct) == "sk-live-1"
    assert report.reencrypted == 1 and session.commits == 1


def test_重跑是冪等的_已是_active_的不再寫入():
    session = SelectQueueSession([[("p1", NEW.encrypt("x"))]])
    report = _run(session, PROVIDER, dry_run=False)
    assert report.already_active == 1 and session.updates() == []


def test_依主鍵分批並逐批_commit():
    batch1 = [("a", OLD.encrypt("1")), ("b", OLD.encrypt("2"))]
    batch2 = [("c", OLD.encrypt("3"))]
    session = SelectQueueSession([batch1, batch2])
    report = _run(session, PROVIDER, dry_run=False, batch_size=2)
    selects = [s for s in session.all_sql() if s.startswith("SELECT")]
    assert "provider_settings.id > ''" in selects[0]
    assert "provider_settings.id > 'b'" in selects[1]
    assert report.reencrypted == 3 and session.commits == 2


def test_單筆解不開時記錄後繼續_且紀錄不含密文():
    broken = "v9:" + OLD.encrypt("x")  # 金鑰 id 不在設定中
    rows = [("p1", broken), ("p2", OLD.encrypt("ok"))]
    session = SelectQueueSession([rows])
    report = _run(session, PROVIDER, dry_run=False)
    assert report.reencrypted == 1
    (failure,) = report.failures
    assert "p1" in failure and "v9" in failure
    assert broken not in failure


def test_通知通道的明文_json_略過不算失敗():
    rows = [("n1", '{"webhook_url": "https://x"}'), ("n2", OLD.encrypt("{}"))]
    session = SelectQueueSession([rows])
    report = _run(session, NOTIFY, dry_run=False)
    assert report.plaintext_skipped == 1 and report.reencrypted == 1
    assert report.failures == []


def test_bot_的_mcp_env_巢狀逐值重寫_其餘欄位不動():
    bindings = [
        {
            "registry_id": "r1",
            "enabled_tools": ["t"],
            "env_values": {"A": OLD.encrypt("a"), "B": NEW.encrypt("b"), "C": ""},
        },
        {"registry_id": "r2", "enabled_tools": []},  # 沒有 env_values
    ]
    session = SelectQueueSession([[("bot-1", bindings)]])
    report = _run(session, BOTS, dry_run=False)
    (stmt,) = session.updates()
    written = _written_value(stmt, "mcp_bindings")
    env = written[0]["env_values"]
    assert NEW.decrypt(env["A"]) == "a" and env["A"].startswith("v2:")
    assert env["B"] == bindings[0]["env_values"]["B"]
    assert env["C"] == ""
    assert written[0]["enabled_tools"] == ["t"]
    assert written[1] == {"registry_id": "r2", "enabled_tools": []}
    assert (report.reencrypted, report.already_active) == (1, 1)


def test_mcp_env_全是_active_時不寫入():
    bindings = [{"registry_id": "r1", "env_values": {"A": NEW.encrypt("a")}}]
    session = SelectQueueSession([[("bot-1", bindings)]])
    _run(session, BOTS, dry_run=False)
    assert session.updates() == []


def test_報表列出每個欄位的待轉筆數():
    session = SelectQueueSession([[("p1", OLD.encrypt("k"))]])
    report = _run(session, PROVIDER, dry_run=True)
    text = format_report([report], dry_run=True, active_id="v2")
    assert "provider_settings.api_key_encrypted" in text
    assert "待轉" in text and "v2" in text


# ---- #107：LINE 憑證的一次性明文 → 密文遷移 ----

LINE_SECRET = next(f for f in ENCRYPTED_FIELDS if f.name == "bots.line_channel_secret")
V1_ONLY = AESEncryptionService(master_key=K1)  # 尚未輪替：active 就是 v1


def test_LINE_憑證的明文在未輪替時也會被加密():
    plain = "0123456789abcdef0123456789abcdef"
    session = SelectQueueSession([[("bot-1", plain), ("bot-2", V1_ONLY.encrypt("s"))]])
    report = _run(session, LINE_SECRET, dry_run=False, svc=V1_ONLY)
    (stmt,) = session.updates()
    written = _written_value(stmt, "line_channel_secret")
    assert written != plain and V1_ONLY.decrypt(written) == plain
    assert (report.plaintext_encrypted, report.already_active) == (1, 1)
    assert report.failures == []


def test_LINE_憑證明文遷移_dry_run_只統計():
    session = SelectQueueSession([[("bot-1", "plain-secret-value")]])
    report = _run(session, LINE_SECRET, dry_run=True, svc=V1_ONLY)
    assert report.plaintext_encrypted == 1 and session.updates() == []
    assert "明文→密文" in format_report([report], dry_run=True, active_id="v1")


def test_LINE_憑證遇到缺金鑰的密文記為失敗_不當明文重加密():
    other = AESEncryptionService(master_key=K2, key_id="v9").encrypt("s")
    session = SelectQueueSession([[("bot-1", other)]])
    report = _run(session, LINE_SECRET, dry_run=False, svc=V1_ONLY)
    assert session.updates() == [] and report.plaintext_encrypted == 0
    (failure,) = report.failures
    assert "v9" in failure


def test_LINE_憑證重跑冪等():
    session = SelectQueueSession([[("bot-1", V1_ONLY.encrypt("s"))]])
    report = _run(session, LINE_SECRET, dry_run=False, svc=V1_ONLY)
    assert session.updates() == [] and report.already_active == 1


# ---- 結束時在 event loop 內釋放連線池（避免 MissingGreenlet 雜訊） ----


def test_run_結束前在_event_loop_內釋放連線池(monkeypatch, capsys):
    """Regression：loop 關閉後才由 GC 關 asyncpg 連線 → MissingGreenlet。"""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    import scripts.reencrypt_secrets as script
    import src.infrastructure.db.engine as engine_mod

    @asynccontextmanager
    async def fake_factory():
        yield SpySession()

    fake_engine = AsyncMock()
    monkeypatch.setattr(engine_mod, "async_session_factory", fake_factory)
    monkeypatch.setattr(engine_mod, "engine", fake_engine)

    assert asyncio.run(script.run(dry_run=True, batch_size=10)) == 0
    fake_engine.dispose.assert_awaited_once()
