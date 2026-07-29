"""LINE 快速道檢索預取 BDD Steps — Issue #52 E3

契約：
1. 預取與 guard/意圖分類並行；查詢未改寫且 KB 未覆寫 → 直接採用預取結果
2. 查詢被改寫 / KB 被覆寫 → 丟棄預取、以正確參數重新檢索（行為同現狀）
3. 無快速道 worker → 不啟動預取；guard 攔截 → 預取結果丟棄
4. 預取失敗 → fail-open 回退正常檢索
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import RetrieveResult
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.worker_config import WorkerConfig
from src.domain.rag.value_objects import Source
from src.domain.security.guard_config import GuardResult

scenarios("unit/line/line_webhook_retrieval_prefetch.feature")

RAW_TEXT = "板橋店有理髮店嗎"
REWRITTEN = "板橋門市 快剪理髮店"
BLOCKED = "我只能協助您處理客服相關問題。"

BODY = (
    '{"events":[{"type":"message","replyToken":"token-pf-001",'
    '"source":{"userId":"U-pf-user"},'
    f'"message":{{"type":"text","text":"{RAW_TEXT}"}},'
    '"timestamp":1700000000000}]}'
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _retrieve_result(score: float = 0.85) -> RetrieveResult:
    return RetrieveResult(
        chunks=["板橋店 2 樓設有快剪理髮店"],
        sources=[
            Source(
                document_name="門市FAQ",
                content_snippet="板橋店 2 樓設有快剪理髮店",
                score=score,
                chunk_id="c-1",
            )
        ],
    )


def _setup(
    context,
    *,
    direct: bool = True,
    rewrite: str = "",
    worker_kb_ids: list[str] | None = None,
    guard_blocked: bool = False,
    first_retrieve_fails: bool = False,
):
    bot = Bot(
        tenant_id="tenant-pf",
        name="PF Bot",
        line_channel_secret="secret-pf",
        line_channel_access_token="token-pf",
        knowledge_base_ids=["kb-faq"],
    )
    worker = WorkerConfig(
        bot_id=bot.id.value,
        name="門市服務查詢",
        worker_prompt="你是門市客服",
        knowledge_base_ids=worker_kb_ids if worker_kb_ids is not None else ["kb-faq"],
        direct_retrieval=direct,
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="板橋店 2 樓有快剪。")
    )
    mock_worker_repo = AsyncMock()
    mock_worker_repo.find_by_bot_id = AsyncMock(return_value=[worker])
    mock_classifier = AsyncMock()

    # 真實分類器是數百 ms 的 LLM 呼叫，預取 task 必然已起跑；
    # AsyncMock 的 await 不會讓出事件迴圈，補一次 sleep(0) 模擬讓出
    async def _classify(*args, **kwargs):
        await asyncio.sleep(0)
        return (worker, rewrite)

    mock_classifier.classify_workers_and_rewrite = AsyncMock(
        side_effect=_classify
    )

    mock_query_rag = AsyncMock()
    if first_retrieve_fails:
        mock_query_rag.retrieve = AsyncMock(
            side_effect=[RuntimeError("milvus hiccup"), _retrieve_result()]
        )
    else:
        mock_query_rag.retrieve = AsyncMock(return_value=_retrieve_result())

    prompt_guard = None
    if guard_blocked:
        prompt_guard = AsyncMock()
        prompt_guard.check_input = AsyncMock(
            return_value=GuardResult(
                passed=False, blocked_response=BLOCKED, rule_matched="ignore_rule"
            )
        )

    context.update(
        use_case=HandleWebhookUseCase(
            agent_service=mock_agent,
            bot_repository=mock_bot_repo,
            line_service_factory=mock_factory,
            intent_classifier=mock_classifier,
            worker_config_repo=mock_worker_repo,
            query_rag_use_case=mock_query_rag,
            prompt_guard=prompt_guard,
        ),
        mock_agent=mock_agent,
        mock_query_rag=mock_query_rag,
        mock_line_service=mock_line_service,
    )


@given("一個開啟直接檢索的 Worker 且分類器未改寫查詢")
def worker_no_rewrite(context):
    _setup(context, rewrite="")


@given("一個開啟直接檢索的 Worker 且分類器將查詢改寫")
def worker_with_rewrite(context):
    _setup(context, rewrite=REWRITTEN)


@given("一個開啟直接檢索且綁定不同知識庫的 Worker")
def worker_other_kb(context):
    _setup(context, worker_kb_ids=["kb-store-only"])


@given("一個未開啟直接檢索的 Worker")
def worker_direct_off(context):
    _setup(context, direct=False)


@given("一個開啟直接檢索的 Worker 且輸入會被 guard 攔截")
def worker_guard_blocked(context):
    _setup(context, guard_blocked=True)


@given("一個開啟直接檢索的 Worker 且第一次檢索會失敗")
def worker_prefetch_fails(context):
    _setup(context, first_retrieve_fails=True)


@when("系統處理一則 LINE 訊息")
def process_message(context):
    _run(context["use_case"].execute_for_bot("PF01", BODY, "sig"))


@then("檢索應只執行一次且查詢為原文")
def retrieve_once_raw(context):
    retrieve = context["mock_query_rag"].retrieve
    retrieve.assert_called_once()
    cmd = retrieve.call_args.args[0]
    assert cmd.query == RAW_TEXT


@then("檢索應執行兩次且最後一次查詢為改寫後查詢")
def retrieve_twice_rewritten(context):
    retrieve = context["mock_query_rag"].retrieve
    assert retrieve.call_count == 2
    cmd = retrieve.call_args.args[0]
    assert cmd.query == REWRITTEN


@then("檢索應執行兩次且最後一次使用 Worker 的知識庫")
def retrieve_twice_worker_kb(context):
    retrieve = context["mock_query_rag"].retrieve
    assert retrieve.call_count == 2
    cmd = retrieve.call_args.args[0]
    assert cmd.kb_ids == ["kb-store-only"]


@then("檢索應執行兩次")
def retrieve_twice(context):
    assert context["mock_query_rag"].retrieve.call_count == 2


@then("不應執行任何檢索")
def no_retrieve(context):
    context["mock_query_rag"].retrieve.assert_not_called()


@then("Agent 應以無工具模式單次生成")
def agent_fast_path(context):
    context["mock_agent"].process_message.assert_called_once()
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert kwargs["enabled_tools"] == []


@then("Agent 應以完整工具模式處理")
def agent_react_path(context):
    context["mock_agent"].process_message.assert_called_once()
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert kwargs["enabled_tools"] != []


@then("不應呼叫 Agent")
def agent_not_called(context):
    context["mock_agent"].process_message.assert_not_called()


@then("應回覆 guard 攔截訊息")
def blocked_reply(context):
    reply = context["mock_line_service"].reply_with_quick_reply
    reply.assert_called_once()
    args_text = str(reply.call_args)
    assert BLOCKED in args_text
