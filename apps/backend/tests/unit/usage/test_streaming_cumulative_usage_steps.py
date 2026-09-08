"""BDD: unit/usage/streaming_cumulative_usage.feature（Issue #90）

Bug 背景（2026-09-08）：
    Gemini 的 OpenAI 相容端點在 stream_options.include_usage 下**每個 chunk 都帶
    累計 usage**；langchain_openai 對任何帶 usage 的 chunk 都掛 usage_metadata，
    langchain_core 合併 AIMessageChunk 時把它們**相加**。結果 kb 模式串流的
    Gemini bot 記帳膨脹：output token 隨回答長度線性放大（實測 1.7 → 7.9 tok/字元，
    terra 平穩 0.85），input 也跟著重複加總（同一份提示記到 4k–15k）。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.llm.openai_compat_chat_model import (
    LastUsageChatOpenAI,
    build_openai_compat_chat_model,
)

scenarios("unit/usage/streaming_cumulative_usage.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


def _chunks(spec: list[tuple[str, dict | None]]) -> list[ChatGenerationChunk]:
    out = []
    for text, usage in spec:
        msg = AIMessageChunk(content=text)
        if usage:
            msg.usage_metadata = {
                "input_tokens": usage["input"],
                "output_tokens": usage["output"],
                "total_tokens": usage["input"] + usage["output"],
            }
        out.append(ChatGenerationChunk(message=msg))
    return out


@given("一個 base_url 指向 googleapis 的相容聊天模型")
def _model(ctx):
    ctx["model"] = build_openai_compat_chat_model(
        model="gemini-x", api_key="k",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        stream_usage=True,
    )


@given(parsers.parse(
    "串流依序回傳三個 chunk，usage 分別為 input {i1:d}/output {o1:d}、"
    "input {i2:d}/output {o2:d}、input {i3:d}/output {o3:d}"
))
def _cumulative(ctx, i1, o1, i2, o2, i3, o3):
    ctx["chunks"] = _chunks([
        ("甲", {"input": i1, "output": o1}),
        ("乙", {"input": i2, "output": o2}),
        ("丙", {"input": i3, "output": o3}),
    ])


@given(parsers.parse(
    "串流依序回傳三個 chunk，只有最後一個帶 usage input {i:d}/output {o:d}"
))
def _final_only(ctx, i, o):
    ctx["chunks"] = _chunks([
        ("甲", None), ("乙", None), ("丙", {"input": i, "output": o}),
    ])


@when("我把串流的 chunk 全部相加成最終訊息")
def _merge(ctx):
    chunks = ctx["chunks"]

    # 只換掉底層 HTTP 串流：父類 _astream 吐什麼，子類就處理什麼
    async def fake_astream(self, messages, stop=None, run_manager=None, **kw: Any):
        for c in chunks:
            yield c

    async def go():
        with patch.object(ChatOpenAI, "_astream", fake_astream):
            final = None
            async for piece in ctx["model"].astream([HumanMessage(content="hi")]):
                final = piece if final is None else final + piece
            return final

    ctx["final"] = _run(go())


@then(parsers.parse("最終訊息的 usage 應為 input {i:d}、output {o:d}"))
def _usage_is(ctx, i, o):
    um = ctx["final"].usage_metadata
    assert um is not None, "最終訊息沒有 usage_metadata"
    assert (um["input_tokens"], um["output_tokens"]) == (i, o), um


@then("最終訊息的文字應為三個 chunk 的內容串接")
def _text_is(ctx):
    assert ctx["final"].content == "甲乙丙"


@when(parsers.parse('我用工廠建立 base_url 為 "{url}" 的模型'))
def _factory(ctx, url):
    ctx["built"] = build_openai_compat_chat_model(model="m", api_key="k", base_url=url)


@then("建出來的模型應為保留最後 usage 的類別")
def _is_last(ctx):
    assert isinstance(ctx["built"], LastUsageChatOpenAI)


@then("建出來的模型應為一般 ChatOpenAI")
def _is_plain(ctx):
    assert type(ctx["built"]) is ChatOpenAI
