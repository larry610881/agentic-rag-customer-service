"""LINE Worker 直接檢索模式（workflow 快速道）BDD Steps — Issue #50

契約：
1. direct_retrieval=true + 檢索過門檻 → agent 以 enabled_tools=[] 單次生成，
   prompt 含檢索結果，回覆 sources 來自快速道
2. 未過門檻 / 檢索異常 → 升級完整 ReAct（原參數）
3. 開關關閉 → 快速道完全不觸發，行為與現狀一致
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

scenarios("unit/line/line_webhook_direct_retrieval.feature")

BODY = (
    '{"events":[{"type":"message","replyToken":"token-dr-001",'
    '"source":{"userId":"U-dr-user"},'
    '"message":{"type":"text","text":"板橋店有理髮店嗎"},'
    '"timestamp":1700000000000}]}'
)

# Issue #51 regression：follow-up 短句，單獨看無法檢索到正確商品
FOLLOWUP_BODY = (
    '{"events":[{"type":"message","replyToken":"token-dr-002",'
    '"source":{"userId":"U-dr-user"},'
    '"message":{"type":"text","text":"價格呢"},'
    '"timestamp":1700000001000}]}'
)
REWRITTEN_QUERY = "活力東勢胡蘿蔔汁 價格"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _sources(score: float) -> list[Source]:
    return [
        Source(
            document_name="門市FAQ",
            content_snippet="板橋店 2 樓設有快剪理髮店",
            score=score,
            chunk_id="c-1",
        )
    ]


def _setup(context, *, direct: bool, top_score: float = 0.85,
           retrieve_raises: bool = False, with_dm: bool = False,
           with_transfer: bool = False, rewrite: str = ""):
    bot = Bot(
        tenant_id="tenant-dr",
        name="DR Bot",
        line_channel_secret="secret-dr",
        line_channel_access_token="token-dr",
        knowledge_base_ids=["kb-faq"],
    )
    worker = WorkerConfig(
        bot_id=bot.id.value,
        name="門市服務查詢",
        worker_prompt="你是門市客服",
        knowledge_base_ids=["kb-faq"],
        direct_retrieval=direct,
        enabled_tools=(
            ["rag_query", "query_dm_with_image"] if with_dm
            else (["rag_query", "transfer_to_human_agent"]
                  if with_transfer else None)
        ),
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
    # Issue #51：LINE 路徑改用 classify_workers_and_rewrite（同呼叫回傳
    # worker + 上下文改寫查詢；改寫缺失時為空字串 → 快速道退回原文）
    mock_classifier.classify_workers_and_rewrite = AsyncMock(
        return_value=(worker, rewrite)
    )

    mock_query_rag = AsyncMock()
    if retrieve_raises:
        mock_query_rag.retrieve = AsyncMock(
            side_effect=RuntimeError("milvus down")
        )
    else:
        mock_query_rag.retrieve = AsyncMock(
            return_value=RetrieveResult(
                chunks=["板橋店 2 樓設有快剪理髮店，營業至 21:00"],
                sources=_sources(top_score),
            )
        )

    mock_dm_tool = AsyncMock()
    mock_dm_tool.invoke = AsyncMock(return_value={
        "success": True,
        "context": "DM 第 49 頁：包大人尿布 特價 299",
        "sources": [{
            "document_name": "DM 型錄",
            "content_snippet": "包大人尿布 特價 299",
            "score": 0.9,
            "chunk_id": "dm-c1",
            "document_id": "dm-d1",
            "page_number": 49,
            "image_url": "https://signed.example/dm-49.png",
        }],
    })

    context.update(
        use_case=HandleWebhookUseCase(
            agent_service=mock_agent,
            bot_repository=mock_bot_repo,
            line_service_factory=mock_factory,
            intent_classifier=mock_classifier,
            worker_config_repo=mock_worker_repo,
            query_rag_use_case=mock_query_rag,
            dm_image_query_tool=mock_dm_tool,
        ),
        mock_agent=mock_agent,
        mock_query_rag=mock_query_rag,
        mock_line_service=mock_line_service,
        mock_dm_tool=mock_dm_tool,
    )


@given("一個開啟直接檢索的 Worker 且檢索結果分數高於門檻")
def worker_direct_high_score(context):
    _setup(context, direct=True, top_score=0.85)


@given("一個開啟直接檢索的 Worker 但檢索結果分數低於門檻")
def worker_direct_low_score(context):
    _setup(context, direct=True, top_score=0.1)


@given("一個開啟直接檢索的 Worker 但檢索過程拋出例外")
def worker_direct_retrieve_error(context):
    _setup(context, direct=True, retrieve_raises=True)


@given("一個未開啟直接檢索的 Worker")
def worker_direct_off(context):
    _setup(context, direct=False)


@when("系統處理一則命中該 Worker 的 LINE 訊息")
def process_message(context):
    _run(context["use_case"].execute_for_bot("DR01", BODY, "sig"))


@then("Agent 應以無工具模式單次生成")
def agent_called_without_tools(context):
    context["mock_agent"].process_message.assert_called_once()
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert kwargs["enabled_tools"] == [], (
        f"快速道應以無工具模式生成，實際 enabled_tools={kwargs['enabled_tools']}"
    )


@then("生成 Prompt 應包含檢索結果")
def prompt_contains_context(context):
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert "快剪理髮店" in (kwargs["system_prompt"] or ""), (
        "快速道 system_prompt 應注入檢索結果"
    )


@then("回覆來源應來自快速道檢索")
def sources_from_direct_retrieval(context):
    # 持久化訊息時 retrieved_chunks 來自 result.sources（快速道回填）
    reply_call = context["mock_line_service"].reply_with_quick_reply
    reply_call.assert_called_once()
    context["mock_query_rag"].retrieve.assert_called_once()


@then("Agent 應以完整工具模式處理")
def agent_called_with_tools(context):
    context["mock_agent"].process_message.assert_called_once()
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert kwargs["enabled_tools"] != [], (
        "升級/關閉情境應以原本工具集處理（完整 ReAct）"
    )


@then("不應執行快速道檢索")
def no_direct_retrieval(context):
    context["mock_query_rag"].retrieve.assert_not_called()


@given("一個開啟直接檢索且啟用 DM 工具的 Worker")
def worker_direct_with_dm(context):
    _setup(context, direct=True, top_score=0.85, with_dm=True)


@then("DM 工具應被並行呼叫")
def dm_tool_invoked(context):
    context["mock_dm_tool"].invoke.assert_called_once()


@then("回覆應附上 DM 圖卡輪播")
def reply_has_dm_carousel(context):
    kwargs = context["mock_line_service"].reply_with_quick_reply.call_args.kwargs
    extra = kwargs.get("extra_messages") or []
    assert any(
        m.get("type") == "flex" and "DM" in (m.get("altText") or "")
        for m in extra
    ), f"應含 DM 圖卡 flex，實際 extra_messages={extra}"


@then("生成 Prompt 應包含 DM 型錄內容")
def prompt_contains_dm_context(context):
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert "包大人尿布 特價 299" in (kwargs["system_prompt"] or ""), (
        "快速道 system_prompt 應注入 DM 型錄內容"
    )


@given("一個開啟直接檢索且啟用轉真人工具的 Worker")
def worker_direct_with_transfer(context):
    _setup(context, direct=True, top_score=0.85, with_transfer=True)


@then("Agent 應僅綁定轉真人工具")
def agent_bound_transfer_only(context):
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert kwargs["enabled_tools"] == ["transfer_to_human_agent"], (
        f"快速道應僅保留轉真人工具，實際 {kwargs['enabled_tools']}"
    )


@then("生成 Prompt 應禁止輸出工具名稱")
def prompt_forbids_tool_name_leak(context):
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    assert "嚴禁在回覆文字中輸出任何工具名稱" in (kwargs["system_prompt"] or "")


@given("一個開啟直接檢索且啟用 DM 工具的 Worker 且意圖分類回傳改寫查詢")
def worker_direct_with_rewrite(context):
    _setup(context, direct=True, top_score=0.85, with_dm=True,
           rewrite=REWRITTEN_QUERY)


@given("一個開啟直接檢索且啟用 DM 工具的 Worker 但意圖分類未回傳改寫查詢")
def worker_direct_without_rewrite(context):
    _setup(context, direct=True, top_score=0.85, with_dm=True, rewrite="")


@when("系統處理一則追問短句的 LINE 訊息")
def process_followup_message(context):
    _run(context["use_case"].execute_for_bot("DR01", FOLLOWUP_BODY, "sig"))


@then("快速道文字檢索應使用改寫後查詢")
def retrieve_uses_rewritten_query(context):
    context["mock_query_rag"].retrieve.assert_called_once()
    cmd = context["mock_query_rag"].retrieve.call_args.args[0]
    assert cmd.query == REWRITTEN_QUERY, (
        f"快速道檢索應使用改寫後查詢，實際 query={cmd.query!r}"
    )


@then("DM 工具應使用改寫後查詢")
def dm_tool_uses_rewritten_query(context):
    context["mock_dm_tool"].invoke.assert_called_once()
    kwargs = context["mock_dm_tool"].invoke.call_args.kwargs
    assert kwargs["query"] == REWRITTEN_QUERY, (
        f"DM 工具應使用改寫後查詢，實際 query={kwargs['query']!r}"
    )


@then("快速道文字檢索應使用使用者原文")
def retrieve_uses_raw_message(context):
    context["mock_query_rag"].retrieve.assert_called_once()
    cmd = context["mock_query_rag"].retrieve.call_args.args[0]
    assert cmd.query == "價格呢", (
        f"改寫缺失時應退回使用者原文，實際 query={cmd.query!r}"
    )


# ---------------------------------------------------------------------------
# 空回覆 regression（2026-08-17 POC 實測：快速道 LLM 呼叫 transfer 後
# max_tool_calls 觸頂 → answer 為空 → LINE reply 400 無聲失敗）
# ---------------------------------------------------------------------------


@given("一個開啟直接檢索且啟用轉真人工具的 Worker 且 Agent 回傳空回答與聯絡卡")
def worker_transfer_empty_answer(context):
    _setup(context, direct=True, with_transfer=True)
    context["mock_agent"].process_message = AsyncMock(
        return_value=AgentResponse(
            answer="",
            contact={"label": "聯絡真人客服", "url": "https://line.me/R/ti/p/@demo",
                     "type": "url"},
        )
    )


@then("LINE 回覆文字不得為空")
def reply_text_not_empty(context):
    context["mock_line_service"].reply_with_quick_reply.assert_called_once()
    args = context["mock_line_service"].reply_with_quick_reply.call_args
    text = args.args[1] if len(args.args) > 1 else args.kwargs.get("text")
    assert text and text.strip(), "空文字送到 LINE 會被 400 拒絕 → 使用者無回應"


@then("回覆應附上聯絡按鈕")
def reply_has_contact(context):
    kwargs = context["mock_line_service"].reply_with_quick_reply.call_args.kwargs
    extra = kwargs.get("extra_messages") or []
    assert any(m.get("altText") == "聯絡真人客服" for m in extra)
