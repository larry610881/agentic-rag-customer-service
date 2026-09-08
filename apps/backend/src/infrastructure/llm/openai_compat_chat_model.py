"""OpenAI 相容端點的 LangChain ChatModel 工廠（Issue #90）。

為什麼需要它：Gemini 的 OpenAI 相容端點在 ``stream_options.include_usage`` 下
**每個 chunk 都帶累計 usage**（OpenAI 只在最後一個 chunk 帶）。langchain_openai
對任何帶 ``usage`` 的 chunk 都掛 ``usage_metadata``，langchain_core 合併
``AIMessageChunk`` 時再把它們**相加**——於是 kb 模式串流的 Gemini bot 記帳隨回答
長度線性膨脹（2026-09-08 實測 output 1.7 → 7.9 tok/字元，terra 平穩 0.85；
input 同一份提示記到 4k–15k）。

做法：對這類供應商，串流時把每個 chunk 的 usage 剝掉、只記住最後一筆，
串流結束後補一個只帶 usage 的空 chunk。這對「只有最後 chunk 帶 usage」的供應商
是等價的，所以用 base_url 判斷即可，不必猜供應商行為。

只在這裡決定「哪個 base_url 要用哪個類別」；兩個建構點
（``openai_llm_service.get_chat_model``、``react_agent_service._create_chat_model``）
都走這個工廠，之後再有同類供應商只改 ``CUMULATIVE_USAGE_HOSTS``。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI

#: 串流時每個 chunk 都帶「累計」usage 的相容端點
CUMULATIVE_USAGE_HOSTS: tuple[str, ...] = ("generativelanguage.googleapis.com",)


def _strip_usage(chunk: ChatGenerationChunk) -> dict | None:
    msg = chunk.message
    usage = getattr(msg, "usage_metadata", None)
    if usage:
        msg.usage_metadata = None
    return usage


def _usage_only_chunk(usage: dict) -> ChatGenerationChunk:
    return ChatGenerationChunk(
        message=AIMessageChunk(content="", usage_metadata=usage)
    )


class LastUsageChatOpenAI(ChatOpenAI):
    """串流只保留最後一筆 usage，避免累計值被逐 chunk 相加。"""

    def _stream(self, *args: Any, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        last: dict | None = None
        for chunk in super()._stream(*args, **kwargs):
            usage = _strip_usage(chunk)
            if usage:
                last = usage
            yield chunk
        if last:
            yield _usage_only_chunk(last)

    async def _astream(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[ChatGenerationChunk]:
        last: dict | None = None
        async for chunk in super()._astream(*args, **kwargs):
            usage = _strip_usage(chunk)
            if usage:
                last = usage
            yield chunk
        if last:
            yield _usage_only_chunk(last)


def uses_cumulative_usage(base_url: str | None) -> bool:
    return bool(base_url) and any(h in base_url for h in CUMULATIVE_USAGE_HOSTS)


def build_openai_compat_chat_model(**kwargs: Any) -> ChatOpenAI:
    """依 ``base_url`` 決定用哪個 ChatOpenAI；參數原封不動往下傳。"""
    if uses_cumulative_usage(kwargs.get("base_url")):
        return LastUsageChatOpenAI(**kwargs)
    return ChatOpenAI(**kwargs)
