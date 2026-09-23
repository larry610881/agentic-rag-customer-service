"""SQLAlchemyConversationRepository — 租戶／父範圍條件與實體映射（Issue #101）。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.infrastructure.db.models.conversation_model import ConversationModel
from src.infrastructure.db.models.message_model import MessageModel
from src.infrastructure.db.repositories.conversation_repository import (
    SQLAlchemyConversationRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _conv_model(**over) -> ConversationModel:
    data: dict = {
        "id": "conv-1",
        "tenant_id": "tenant-a",
        "bot_id": "bot-1",
        "visitor_id": "v-1",
        "created_at": T0,
        "summary": "摘要",
        "message_count": 4,
        "summary_message_count": 2,
        "last_message_at": T0,
        "summary_at": T0,
    }
    data.update(over)
    return ConversationModel(**data)


def _msg_model(**over) -> MessageModel:
    data: dict = {
        "id": "m-1",
        "conversation_id": "conv-1",
        "role": "assistant",
        "content": "答",
        "tool_calls_json": json.dumps([{"name": "rag"}]),
        "latency_ms": 120,
        "retrieved_chunks": json.dumps([{"id": "c1"}]),
        "structured_content": json.dumps({"sources": []}),
        "created_at": T0,
    }
    data.update(over)
    return MessageModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyConversationRepository:
    return SQLAlchemyConversationRepository(session)  # type: ignore[arg-type]


def test_find_recent_user_questions_scoped_to_bot_and_tenant(session, repo):
    class Row:
        def __init__(self, content):
            self.content = content

    session.queue_result([Row("運費?"), Row("營業時間")])
    out = _run(repo.find_recent_user_questions("bot-1", "tenant-a", limit=2))
    sql = session.sql(0)
    assert "conversations.bot_id = 'bot-1'" in sql
    assert "conversations.tenant_id = 'tenant-a'" in sql
    assert "messages.role = 'user'" in sql
    assert out == ["運費?", "營業時間"]


def test_find_by_tenant_filters_tenant_and_bot(session, repo):
    session.queue_result([_conv_model()])
    (conv,) = _run(repo.find_by_tenant("tenant-a", bot_id="bot-1", limit=5, offset=5))
    sql = session.sql(0)
    assert "conversations.tenant_id = 'tenant-a'" in sql
    assert "conversations.bot_id = 'bot-1'" in sql
    assert "LIMIT 5" in sql and "OFFSET 5" in sql
    assert conv.id.value == "conv-1"
    assert conv.tenant_id == "tenant-a"
    assert conv.messages == []
    assert conv.summary == "摘要"
    assert conv.message_count == 4


def test_find_by_tenant_without_bot(session, repo):
    _run(repo.find_by_tenant("tenant-a"))
    sql = session.sql(0)
    assert "conversations.tenant_id = 'tenant-a'" in sql
    assert "bot_id =" not in sql


def test_count_by_tenant_filters(session, repo):
    session.queue_result([3])
    assert _run(repo.count_by_tenant("tenant-a", bot_id="bot-1")) == 3
    sql = session.sql(0)
    assert "conversations.tenant_id = 'tenant-a'" in sql
    assert "conversations.bot_id = 'bot-1'" in sql
    _run(repo.count_by_tenant("tenant-a"))
    assert "bot_id" not in session.sql(-1).split("WHERE")[1]


def test_find_by_id_loads_messages_scoped_to_conversation(session, repo):
    session.get_result = _conv_model()
    session.queue_result([_msg_model(), _msg_model(
        id="m-0", role="user", retrieved_chunks=None, structured_content=None,
        tool_calls_json="[]",
    )])

    conv = _run(repo.find_by_id("conv-1"))

    assert "messages.conversation_id = 'conv-1'" in session.sql(0)
    assert conv is not None
    assert conv.tenant_id == "tenant-a"
    assert conv.visitor_id == "v-1"
    m1, m0 = conv.messages
    assert m1.tool_calls == [{"name": "rag"}]
    assert m1.retrieved_chunks == [{"id": "c1"}]
    assert m1.structured_content == {"sources": []}
    assert m1.latency_ms == 120
    assert m0.retrieved_chunks is None and m0.structured_content is None


def test_find_by_id_missing_returns_none_without_query(session, repo):
    assert _run(repo.find_by_id("x")) is None
    assert session.statements == []


def test_find_latest_by_visitor_scoped_to_visitor_and_bot(session, repo):
    session.queue_result([_conv_model()])
    session.queue_result([_msg_model(retrieved_chunks=None, structured_content=None)])

    conv = _run(repo.find_latest_by_visitor("v-1", "bot-1"))

    conv_sql, msg_sql = session.all_sql()
    assert "conversations.visitor_id = 'v-1'" in conv_sql
    assert "conversations.bot_id = 'bot-1'" in conv_sql
    assert "LIMIT 1" in conv_sql
    assert "messages.conversation_id = 'conv-1'" in msg_sql
    assert conv is not None and conv.bot_id == "bot-1"
    (msg,) = conv.messages
    assert msg.retrieved_chunks is None


def test_find_latest_by_visitor_none(session, repo):
    assert _run(repo.find_latest_by_visitor("v-1", "bot-1")) is None
    assert len(session.statements) == 1


def test_find_conversation_id_by_message(session, repo):
    session.queue_result(["conv-1"])
    assert _run(repo.find_conversation_id_by_message("m-1")) == "conv-1"
    assert "messages.id = 'm-1'" in session.sql(0)


def test_find_pending_summary_conditions(session, repo):
    session.queue_result(["conv-1", "conv-2"])
    ids = _run(repo.find_pending_summary(idle_minutes=5, limit=10, min_message_count=3))
    sql = session.sql(0)
    assert "conversations.last_message_at IS NOT NULL" in sql
    assert "conversations.message_count >= 3" in sql
    assert "conversations.summary IS NULL" in sql
    assert "LIMIT 10" in sql
    assert ids == ["conv-1", "conv-2"]


def test_search_summary_by_keyword_with_tenant_and_bot(session, repo):
    session.queue_result([_conv_model()])
    (conv,) = _run(
        repo.search_summary_by_keyword(keyword="退貨", tenant_id="tenant-a",
                                       bot_id="bot-1", limit=3)
    )
    sql = session.sql(0)
    assert "conversations.tenant_id = 'tenant-a'" in sql
    assert "conversations.bot_id = 'bot-1'" in sql
    assert "ILIKE '%%退貨%%'" in sql or "ILIKE '%退貨%'" in sql
    assert conv.visitor_id == "v-1"


def test_search_summary_by_keyword_admin_cross_tenant(session, repo):
    # system_admin 端點（admin_router require_role）才會省略 tenant_id
    _run(repo.search_summary_by_keyword(keyword="x"))
    assert "tenant_id =" not in session.sql(0)


def test_find_by_ids(session, repo):
    assert _run(repo.find_by_ids([])) == []
    assert session.statements == []
    session.queue_result([_conv_model()])
    (conv,) = _run(repo.find_by_ids(["conv-1"]))
    assert "conversations.id IN ('conv-1')" in session.sql(0)
    assert conv.summary_at == T0


def test_save_new_conversation_adds_models_for_new_messages(session, repo):
    conv = Conversation(
        id=ConversationId(value="conv-9"),
        tenant_id="tenant-a",
        bot_id="bot-1",
        visitor_id="v-1",
        messages=[
            Message(id=MessageId(value="m-old"), conversation_id="conv-9",
                    role="user", content="舊"),
            Message(id=MessageId(value="m-new"), conversation_id="conv-9",
                    role="assistant", content="新", retrieved_chunks=[{"id": 1}],
                    structured_content={"k": "中"}),
        ],
    )
    session.queue_result(["m-old"])  # 已存在的 message id

    _run(repo.save(conv))

    assert "messages.id IN ('m-old', 'm-new')" in session.sql(0)
    conv_model, msg_model = session.added
    assert isinstance(conv_model, ConversationModel)
    assert conv_model.tenant_id == "tenant-a"
    assert isinstance(msg_model, MessageModel)
    assert msg_model.id == "m-new"
    assert json.loads(msg_model.retrieved_chunks) == [{"id": 1}]
    assert "中" in msg_model.structured_content
    assert session.commits == 1


def test_save_existing_updates_summary_and_backfills_visitor(session, repo):
    existing = _conv_model(visitor_id=None, summary=None)
    session.get_result = existing
    conv = Conversation(
        id=ConversationId(value="conv-1"), tenant_id="tenant-a",
        visitor_id="v-2", summary="新摘要", message_count=6,
        summary_message_count=6, last_message_at=T0, summary_at=T0,
    )

    _run(repo.save(conv))

    assert existing.visitor_id == "v-2"
    assert existing.summary == "新摘要"
    assert existing.message_count == 6
    assert existing.tenant_id == "tenant-a"  # 租戶不被 save 改寫
    assert session.added == []
    assert session.statements == []  # 無 messages → 不查
