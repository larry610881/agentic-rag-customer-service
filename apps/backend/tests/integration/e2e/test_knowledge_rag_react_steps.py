"""E2E Journey: 知識庫 → RAG → ReAct Agent 完整旅程"""

from pytest_bdd import given, parsers, scenarios, then, when

from tests.integration.e2e.conftest import (
    create_bot,
    create_kb,
    create_tenant_and_login,
    send_chat,
    upload_doc,
)

scenarios("e2e/knowledge_rag_react_flow.feature")


# -----------------------------------------------------------------------
# Steps
# -----------------------------------------------------------------------


@given(
    parsers.parse('已建立租戶 "{name}" 並取得 token 並啟用 react'),
    target_fixture="ctx",
)
def setup_tenant_react(e2e_client, e2e_app, name):
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
        "退貨流程：步驟一、聯繫客服。步驟二、填寫退貨單。步驟三、寄回商品。",
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
    )


@given(
    parsers.parse(
        '已建立 Bot "{name}" 綁定知識庫 agent_mode 為 "{mode}" max_tool_calls 為 {max_calls:d}'
    )
)
def setup_bot_max_calls(ctx, name, mode, max_calls):
    ctx["bot_id"] = create_bot(
        ctx["client"],
        ctx["headers"],
        name,
        [ctx["kb_id"]],
        max_tool_calls=max_calls,
    )


@when(parsers.parse('我透過 Bot 發送對話 "{message}"'))
def send_message(ctx, message):
    result = send_chat(
        ctx["client"], ctx["headers"], ctx["bot_id"], message
    )
    ctx["response"] = result


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"]["status_code"] == code, (
        f"Expected {code}, got {ctx['response']['status_code']}: "
        f"{ctx['response']}"
    )


@then("回答應非空")
def check_answer_not_empty(ctx):
    answer = ctx["response"]["answer"]
    assert answer, "Answer should not be empty"


@then(parsers.parse('tool_calls 應包含 "{tool_name}"'))
def check_tool_calls_contain(ctx, tool_name):
    tool_calls = ctx["response"].get("tool_calls", [])
    tool_names = [tc["tool_name"] for tc in tool_calls]
    assert tool_name in tool_names, (
        f"Expected tool_calls to contain '{tool_name}', "
        f"got {tool_names}"
    )


@then(parsers.parse("tool_calls 數量不應超過 {max_count:d}"))
def check_tool_calls_count(ctx, max_count):
    tool_calls = ctx["response"].get("tool_calls", [])
    # Filter out "direct" entries
    real_calls = [tc for tc in tool_calls if tc["tool_name"] != "direct"]
    assert len(real_calls) <= max_count, (
        f"Expected at most {max_count} tool calls, got {len(real_calls)}: "
        f"{[tc['tool_name'] for tc in real_calls]}"
    )
