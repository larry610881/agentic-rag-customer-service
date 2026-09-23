"""Regression：bots 表的 LINE 憑證 at-rest 加密（Issue #107）。

舊碼把 line_channel_secret / line_channel_access_token 明文寫進 DB；DB 備份、唯讀帳號或
SQL 注入任一外洩就等於 LINE 官方帳號被接管。改為 repository 層加解密：
- 寫入一律是密文（active 金鑰）
- 讀出還原為明文（domain 與各通路不受影響）
- 既有明文資料照樣可讀（遷移前資料），之後由存檔或 reencrypt 腳本轉為密文
- 金鑰 id 不在設定中 → 直接報錯，不可當明文吞掉（否則後台存檔會把憑證洗成亂碼或空值）
"""

from __future__ import annotations

import asyncio

import pytest

from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.value_objects import BotId, BotShortCode
from src.infrastructure.crypto.aes_encryption_service import (
    AESEncryptionService,
    UnknownEncryptionKeyError,
)
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.repositories.bot_repository import SQLAlchemyBotRepository
from tests.unit.repositories.spy_session import SpySession
from tests.unit.repositories.test_bot_repository import _model

K1 = "11" * 32
K2 = "22" * 32
ENC = AESEncryptionService(master_key=K1)
SECRET = "0123456789abcdef0123456789abcdef"
TOKEN = "Zx" * 86  # 長度同 LINE 長效 access token（約 172 字元）


def _run(coro):
    return asyncio.run(coro)


def _bot(**over) -> Bot:
    data: dict = {
        "id": BotId(value="bot-1"),
        "short_code": BotShortCode(value="abc123"),
        "tenant_id": "tenant-a",
        "name": "b",
        "knowledge_base_ids": [],
        "llm_params": BotLLMParams(),
        "line_channel_secret": SECRET,
        "line_channel_access_token": TOKEN,
    }
    data.update(over)
    return Bot(**data)


def _repo(session: SpySession, enc: AESEncryptionService = ENC):
    return SQLAlchemyBotRepository(session, encryption=enc)  # type: ignore[arg-type]


def test_新建_bot_時憑證以密文寫入():
    session = SpySession()
    _run(_repo(session).save(_bot()))
    (m,) = [o for o in session.added if isinstance(o, BotModel)]
    assert m.line_channel_secret != SECRET and m.line_channel_access_token != TOKEN
    assert ENC.decrypt(m.line_channel_secret) == SECRET
    assert ENC.decrypt(m.line_channel_access_token) == TOKEN


def test_更新既有_bot_時憑證以密文寫入():
    session = SpySession()
    existing = _model(line_channel_secret="old", line_channel_access_token="old")
    session.get_result = existing
    _run(_repo(session).save(_bot()))
    assert ENC.decrypt(existing.line_channel_secret) == SECRET
    assert ENC.decrypt(existing.line_channel_access_token) == TOKEN


def test_讀出時還原為明文():
    session = SpySession()
    session.queue_result(
        [
            _model(
                line_channel_secret=ENC.encrypt(SECRET),
                line_channel_access_token=ENC.encrypt(TOKEN),
            )
        ]
    )
    session.queue_result([])  # kb ids
    bot = _run(_repo(session).find_by_id("bot-1"))
    assert bot is not None
    assert (bot.line_channel_secret, bot.line_channel_access_token) == (SECRET, TOKEN)


def test_遷移前的明文資料照樣可讀():
    session = SpySession()
    session.queue_result(
        [_model(line_channel_secret=SECRET, line_channel_access_token=TOKEN)]
    )
    session.queue_result([])
    bot = _run(_repo(session).find_by_id("bot-1"))
    assert bot is not None
    assert (bot.line_channel_secret, bot.line_channel_access_token) == (SECRET, TOKEN)


def test_空值維持空值():
    session = SpySession()
    bot = _bot(line_channel_secret=None, line_channel_access_token="")
    _run(_repo(session).save(bot))
    (m,) = [o for o in session.added if isinstance(o, BotModel)]
    assert m.line_channel_secret is None and m.line_channel_access_token == ""


def test_金鑰_id_不在設定中時報錯_不當明文吞掉():
    rotated = AESEncryptionService(master_key=K2, key_id="v2", previous_keys=f"v1:{K1}")
    session = SpySession()
    session.queue_result([_model(line_channel_secret=rotated.encrypt(SECRET))])
    session.queue_result([])
    with pytest.raises(UnknownEncryptionKeyError):
        _run(_repo(session, enc=ENC).find_by_id("bot-1"))


def test_加密後的_access_token_超過_255_字元_欄位必須是_TEXT():
    """VARCHAR(255) 放不下；migration 將兩欄改為 TEXT。"""
    assert len(ENC.encrypt(TOKEN)) > 255
    col = BotModel.__table__.c
    assert col.line_channel_access_token.type.length is None
    assert col.line_channel_secret.type.length is None
