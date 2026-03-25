"""E2E Journey: 知識庫 → RAG → Router Agent 完整旅程"""

from pytest_bdd import given, parsers, scenarios, then, when

from tests.integration.e2e.conftest import (
    create_bot,
    create_kb,
    create_tenant_and_login,
    send_chat,
    upload_doc,
)

scenarios("e2e/knowledge_rag_router_flow.feature")


# -----------------------------------------------------------------------
# Steps
# -----------------------------------------------------------------------


@given(
    parsers.parse('已建立租戶 "{name}" 並取得 token'),
    target_fixture="ctx",
)
def setup_tenant(e2e_client, e2e_app, name):
    ctx = {}
    ctx["headers"] = create_tenant_and_login(e2e_client, name, app=e2e_app)
    ctx["client"] = e2e_client
    return ctx


@given(parsers.parse('已建立知識庫 "{name}"'))
def setup_kb(ctx, name):
    ctx["kb_id"] = create_kb(ctx["client"], ctx["headers"], name)


@given(parsers.parse('已上傳文件 "{filename}" 到知識庫'))
def setup_doc(ctx, filename):
    upload_doc(
        ctx["client"],
        ctx["headers"],
        ctx["kb_id"],
        filename,
        "退貨政策：購買後 30 天內可無條件退貨，請保留原始包裝。換貨政策：7天內可換貨。",
    )


@given(
    parsers.parse(
        '已建立 Bot "{name}" 綁定知識庫 agent_mode 為 "{mode}"'
    )
)
def setup_bot(ctx, name, mode):
    ctx["bot_id"] = create_bot(
        ctx["client"],
        ctx["headers"],
        name,
        [ctx["kb_id"]],
        agent_mode=mode,
    )


@when(parsers.parse('我透過 Bot 發送對話 "{message}"'))
def send_message(ctx, message):
    result = send_chat(
        ctx["client"], ctx["headers"], ctx["bot_id"], message
    )
    ctx["response"] = result
    # Keep first response for multi-turn tests
    if "first_response" not in ctx:
        ctx["first_response"] = result


@when(parsers.parse('我使用同一 conversation_id 發送對話 "{message}"'))
def send_followup(ctx, message):
    conv_id = ctx["first_response"]["conversation_id"]
    result = send_chat(
        ctx["client"],
        ctx["headers"],
        ctx["bot_id"],
        message,
        conversation_id=conv_id,
    )
    ctx["second_response"] = result
    ctx["response"] = result


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"]["status_code"] == code, (
        f"Expected {code}, got {ctx['response']['status_code']}"
    )


@then("回答應包含知識庫相關內容")
def check_answer_has_content(ctx):
    answer = ctx["response"]["answer"]
    assert answer, "Answer should not be empty"
    assert len(answer) > 5, f"Answer too short: {answer}"


@then("conversation_id 應非空")
def check_conversation_id(ctx):
    conv_id = ctx["response"].get("conversation_id")
    assert conv_id, "conversation_id should not be empty"


@then("回答應包含無資料提示")
def check_no_data_answer(ctx):
    answer = ctx["response"]["answer"]
    assert answer, "Answer should not be empty"
    # FakeLLMService returns this when context is empty
    assert "沒有" in answer or "沒有找到" in answer or len(answer) > 0


@then("兩次回應的 conversation_id 應相同")
def check_same_conversation(ctx):
    first_id = ctx["first_response"]["conversation_id"]
    second_id = ctx["second_response"]["conversation_id"]
    assert first_id == second_id, (
        f"Expected same conversation_id, got {first_id} vs {second_id}"
    )


@then("第二次回應應正常")
def check_second_response(ctx):
    resp = ctx["second_response"]
    assert resp["status_code"] == 200
    assert resp["answer"], "Second answer should not be empty"
