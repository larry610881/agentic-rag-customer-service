"""SQLAlchemyFeedbackRepository — 租戶過濾條件與實體映射（Issue #101）。

另含 SubmitFeedbackUseCase 的跨租戶覆寫 regression：find_by_message_id 不帶租戶，
呼叫端必須自己擋「他租戶既有回饋」。
"""

from __future__ import annotations

import asyncio
import json
from collections import namedtuple
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackCommand,
    SubmitFeedbackUseCase,
)
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.db.models.feedback_model import FeedbackModel
from src.infrastructure.db.models.message_model import MessageModel
from src.infrastructure.db.repositories.feedback_repository import (
    SQLAlchemyFeedbackRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> FeedbackModel:
    data: dict = {
        "id": "fb-1",
        "tenant_id": "tenant-a",
        "conversation_id": "conv-1",
        "message_id": "msg-1",
        "user_id": "u-1",
        "channel": "web",
        "rating": "thumbs_down",
        "comment": "答錯",
        "tags": json.dumps(["不準確"], ensure_ascii=False),
        "retrieval_quality": "low",
        "created_at": T0,
    }
    data.update(over)
    return FeedbackModel(**data)


def _entity(**over) -> Feedback:
    data: dict = {
        "id": FeedbackId(value="fb-1"),
        "tenant_id": "tenant-a",
        "conversation_id": "conv-1",
        "message_id": "msg-1",
        "user_id": "u-1",
        "channel": Channel.WEB,
        "rating": Rating.THUMBS_UP,
        "comment": "好",
        "tags": ["有幫助", "中文"],
        "retrieval_quality": "high",
        "created_at": T0,
    }
    data.update(over)
    return Feedback(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyFeedbackRepository:
    return SQLAlchemyFeedbackRepository(session)  # type: ignore[arg-type]


# ---- 寫入 ----


def test_save_adds_model_with_tenant_and_json_tags(session, repo):
    _run(repo.save(_entity()))

    (added,) = session.added
    assert isinstance(added, FeedbackModel)
    assert added.tenant_id == "tenant-a"
    assert added.message_id == "msg-1"
    assert added.channel == "web"
    assert added.rating == "thumbs_up"
    assert json.loads(added.tags) == ["有幫助", "中文"]
    assert "中文" in added.tags  # ensure_ascii=False
    assert session.commits == 1


def test_update_mutates_loaded_model(session, repo):
    model = _model()
    session.queue_result([model])

    _run(repo.update(_entity(comment="改觀", tags=["x"])))

    assert "feedback.id = 'fb-1'" in session.sql(0)
    assert model.rating == "thumbs_up"
    assert model.comment == "改觀"
    assert json.loads(model.tags) == ["x"]
    assert model.retrieval_quality == "high"


def test_update_missing_row_is_noop(session, repo):
    _run(repo.update(_entity()))
    assert session.added == []
    assert len(session.statements) == 1


def test_update_tags_binds_tenant_when_given(session, repo):
    model = _model(tags=json.dumps(["a"]))
    session.queue_result([model])

    _run(repo.update_tags("msg-1", ["a", "b"], tenant_id="tenant-a"))

    sql = session.sql(0)
    assert "feedback.message_id = 'msg-1'" in sql
    assert "feedback.tenant_id = 'tenant-a'" in sql
    # 合併去重、保留順序
    assert json.loads(model.tags) == ["a", "b"]


def test_update_tags_without_row_does_nothing(session, repo):
    _run(repo.update_tags("msg-x", ["a"], tenant_id="tenant-a"))
    assert "feedback.tenant_id = 'tenant-a'" in session.sql(0)


def test_delete_before_date_scoped_to_tenant(session, repo):
    session.queue_result(rowcount=7)

    deleted = _run(repo.delete_before_date("tenant-a", T0))

    sql = session.sql(0)
    assert sql.startswith("DELETE FROM feedback")
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "feedback.created_at <" in sql
    assert deleted == 7


# ---- 讀取：租戶過濾 ----


def test_find_by_tenant_filters_tenant_and_maps_entity(session, repo):
    session.queue_result([_model()])

    items = _run(repo.find_by_tenant("tenant-a", limit=5, offset=10))

    sql = session.sql(0)
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 5" in sql and "OFFSET 10" in sql
    (fb,) = items
    assert fb.id.value == "fb-1"
    assert fb.tenant_id == "tenant-a"
    assert fb.channel is Channel.WEB
    assert fb.rating is Rating.THUMBS_DOWN
    assert fb.tags == ["不準確"]
    assert fb.retrieval_quality == "low"
    assert fb.created_at == T0


def test_find_by_conversation_scoped_by_conversation(session, repo):
    session.queue_result([_model()])
    (fb,) = _run(repo.find_by_conversation("conv-1"))
    assert "feedback.conversation_id = 'conv-1'" in session.sql(0)
    assert fb.conversation_id == "conv-1"


def test_find_by_message_id_maps_or_none(session, repo):
    assert _run(repo.find_by_message_id("msg-x")) is None
    session.queue_result([_model()])
    fb = _run(repo.find_by_message_id("msg-1"))
    assert fb is not None and fb.message_id == "msg-1"
    assert "feedback.message_id = 'msg-1'" in session.sql(-1)


def test_count_by_tenant_and_rating_all_filters(session, repo):
    session.queue_result([4])
    n = _run(
        repo.count_by_tenant_and_rating(
            "tenant-a",
            Rating.THUMBS_UP,
            start_date=T0,
            end_date=T0 + timedelta(days=1),
        )
    )
    sql = session.sql(0)
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "feedback.rating = 'thumbs_up'" in sql
    assert "feedback.created_at >=" in sql
    assert "feedback.created_at <" in sql
    assert n == 4


def test_count_by_tenant_without_optional_filters(session, repo):
    _run(repo.count_by_tenant_and_rating("tenant-a"))
    sql = session.sql(0)
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "feedback.rating" not in sql.split("WHERE", 1)[1]


def test_get_daily_trend_filters_tenant_and_computes_pct(session, repo):
    Row = namedtuple("Row", "dt total positive negative")
    session.queue_result(
        [Row(date(2026, 9, 1), 4, 3, 1), Row(date(2026, 9, 2), 0, 0, 0)]
    )

    stats = _run(
        repo.get_daily_trend("tenant-a", start_date=T0, end_date=T0)
    )

    sql = session.sql(0)
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "feedback.created_at >=" in sql and "feedback.created_at <" in sql
    assert stats[0].satisfaction_pct == 75.0
    assert (stats[0].total, stats[0].positive, stats[0].negative) == (4, 3, 1)
    assert stats[1].satisfaction_pct == 0.0


def test_get_top_tags_counts_negative_tags_of_tenant(session, repo):
    session.queue_result(
        [json.dumps(["慢", "錯"]), json.dumps(["錯"]), json.dumps([])]
    )

    tags = _run(repo.get_top_tags("tenant-a", start_date=T0, end_date=T0, limit=1))

    sql = session.sql(0)
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "feedback.rating = 'thumbs_down'" in sql
    assert [(t.tag, t.count) for t in tags] == [("錯", 2)]


def test_count_negative_filters_tenant(session, repo):
    session.queue_result([2])
    assert _run(repo.count_negative("tenant-a", days=7)) == 2
    sql = session.sql(0)
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "feedback.rating = 'thumbs_down'" in sql


def test_find_by_date_range_filters_tenant(session, repo):
    session.queue_result([_model()])
    (fb,) = _run(repo.find_by_date_range("tenant-a", T0, T0))
    sql = session.sql(0)
    assert "feedback.tenant_id = 'tenant-a'" in sql
    assert "feedback.created_at >=" in sql and "feedback.created_at <=" in sql
    assert fb.tenant_id == "tenant-a"


def test_get_negative_with_context_empty_stops_after_first_query(session, repo):
    assert _run(repo.get_negative_with_context("tenant-a")) == []
    assert len(session.statements) == 1
    assert "feedback.tenant_id = 'tenant-a'" in session.sql(0)


def test_get_negative_with_context_assembles_records(session, repo):
    FbRow = namedtuple("FbRow", "message_id rating comment created_at")
    session.queue_result(
        [
            FbRow("asst-1", "thumbs_down", "錯", T0),
            FbRow("asst-gone", "thumbs_down", None, T0),
        ]
    )
    asst = MessageModel(
        id="asst-1",
        conversation_id="conv-1",
        role="assistant",
        content="答案",
        retrieved_chunks=json.dumps([{"id": "c1"}]),
        created_at=T0,
    )
    session.queue_result([asst])
    later_user = MessageModel(
        id="u-late", conversation_id="conv-1", role="user", content="之後",
        created_at=T0 + timedelta(minutes=1),
    )
    user = MessageModel(
        id="u-1", conversation_id="conv-1", role="user", content="問題",
        created_at=T0 - timedelta(minutes=1),
    )
    session.queue_result([later_user, user])

    records = _run(repo.get_negative_with_context("tenant-a", limit=2, offset=0))

    feedback_sql, asst_sql, user_sql = session.all_sql()
    assert "feedback.tenant_id = 'tenant-a'" in feedback_sql
    # 後兩段以第一段（已租戶過濾）拿到的 id 為範圍
    assert "messages.id IN ('asst-1', 'asst-gone')" in asst_sql
    assert "messages.conversation_id IN ('conv-1')" in user_sql
    (rec,) = records
    assert rec.user_question == "問題"
    assert rec.assistant_answer == "答案"
    assert rec.retrieved_chunks == [{"id": "c1"}]
    assert rec.comment == "錯"


# ---- Regression：SubmitFeedbackUseCase 跨租戶覆寫他租戶回饋 ----


def _submit_use_case(
    session: SpySession, conv_tenant: str, message_ids: tuple[str, ...] = ("msg-a",)
) -> SubmitFeedbackUseCase:
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = Conversation(
        id=ConversationId(value="conv-a"),
        tenant_id=conv_tenant,
        messages=[
            Message(
                id=MessageId(value=mid),
                conversation_id="conv-a",
                role="assistant",
                content="答",
            )
            for mid in message_ids
        ],
    )
    return SubmitFeedbackUseCase(
        feedback_repository=SQLAlchemyFeedbackRepository(session),  # type: ignore[arg-type]
        conversation_repository=conv_repo,
    )


def test_submit_feedback_cannot_overwrite_other_tenants_feedback(session):
    """租戶 A 以自己的對話 id + 租戶 B 訊息的 message_id 提交回饋。

    修正前：find_by_message_id 不分租戶撈到 B 的回饋並直接改寫 rating/comment/tags。
    """
    victim = _model(
        tenant_id="tenant-b", message_id="msg-b", rating="thumbs_up",
        comment="B 的原評論", tags="[]",
    )
    session.queue_result([victim])
    # 把 msg-b 放進 A 的對話，讓測試越過「訊息屬於對話」檢查，
    # 專門驗第二道防線：既有回饋屬於別的租戶也不可改寫
    use_case = _submit_use_case(
        session, conv_tenant="tenant-a", message_ids=("msg-a", "msg-b")
    )

    with pytest.raises(EntityNotFoundError):
        _run(
            use_case.execute(
                SubmitFeedbackCommand(
                    tenant_id="tenant-a",
                    conversation_id="conv-a",
                    message_id="msg-b",
                    channel="widget",
                    rating="thumbs_down",
                    comment="injected",
                    tags=["spam"],
                )
            )
        )

    assert victim.rating == "thumbs_up"
    assert victim.comment == "B 的原評論"
    assert victim.tags == "[]"
    assert session.added == []


def test_submit_feedback_same_tenant_upsert_still_updates(session):
    own = _model(tenant_id="tenant-a", message_id="msg-a", rating="thumbs_up")
    session.queue_result([own])  # find_by_message_id
    session.queue_result([own])  # update() 內再 select
    use_case = _submit_use_case(session, conv_tenant="tenant-a")

    fb = _run(
        use_case.execute(
            SubmitFeedbackCommand(
                tenant_id="tenant-a",
                conversation_id="conv-a",
                message_id="msg-a",
                channel="web",
                rating="thumbs_down",
            )
        )
    )

    assert fb.rating is Rating.THUMBS_DOWN
    assert own.rating == "thumbs_down"
