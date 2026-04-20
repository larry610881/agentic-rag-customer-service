"""Contextual Retrieval: generate document context per chunk using LLM.

Anthropic's research shows this improves retrieval accuracy by ~35%.
Supports any provider via call_llm (Anthropic, OpenAI, LiteLLM, etc.).
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import ChunkContextService
from src.infrastructure.llm.llm_caller import call_llm
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

CONTEXT_PROMPT = """\
<document>
{document_content}
</document>

以下是文件中的一個片段：
<chunk>
{chunk_content}
</chunk>

請用 1-2 句繁體中文描述這個片段在文件中的位置和上下文。只輸出描述，不要其他內容。"""

DEFAULT_MODEL = "anthropic:claude-haiku-4-5-20251001"
MAX_CONCURRENCY = 5
MAX_DOC_CHARS = 100_000


class LLMChunkContextService(ChunkContextService):
    def __init__(
        self,
        api_key: str = "",
        api_key_resolver: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._api_key_resolver = api_key_resolver
        # Token-Gov.0: 累計每次 generate_contexts 的 token 用量。
        # process_document_use_case 會在跑完讀這 3 個屬性 → record_usage。
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0
        self.last_model: str = ""

    async def generate_contexts(
        self,
        document_content: str,
        chunks: list[Chunk],
        model: str = "",
    ) -> list[Chunk]:
        if not chunks or not document_content.strip():
            return chunks

        # 重置 token 累計（每次呼叫獨立計算）
        self.last_input_tokens = 0
        self.last_output_tokens = 0

        model = model or DEFAULT_MODEL
        self.last_model = model
        doc_text = document_content[:MAX_DOC_CHARS]

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        log = logger.bind(model=model, chunk_count=len(chunks))
        log.info("context.generation.start")

        # Pre-resolve API key once to avoid concurrent session conflicts
        from src.infrastructure.llm.llm_caller import _parse_model_spec
        provider, _ = _parse_model_spec(model)
        resolved_key = ""
        if self._api_key_resolver:
            resolved_key = await self._api_key_resolver(provider)

        async def _fixed_key_resolver(_provider: str) -> str:
            return resolved_key

        async def _generate_one(chunk: Chunk) -> Chunk:
            async with sem:
                try:
                    prompt = CONTEXT_PROMPT.format(
                        document_content=doc_text,
                        chunk_content=chunk.content,
                    )
                    result = await call_llm(
                        model_spec=model,
                        prompt=prompt,
                        max_tokens=200,
                        api_key_resolver=_fixed_key_resolver,
                    )
                    # Token-Gov.0: 累計每 chunk 的 token（asyncio.gather 並發安全：
                    # CPython GIL 保護 int 加法，且 sem 限制並發 ≤5）
                    self.last_input_tokens += result.input_tokens
                    self.last_output_tokens += result.output_tokens
                    return Chunk(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        tenant_id=chunk.tenant_id,
                        content=chunk.content,
                        context_text=result.text,
                        chunk_index=chunk.chunk_index,
                        metadata=chunk.metadata,
                    )
                except Exception:
                    log.warning(
                        "context.generation.chunk_failed",
                        chunk_id=chunk.id.value,
                        exc_info=True,
                    )
                    return chunk

        results = await asyncio.gather(*[_generate_one(c) for c in chunks])
        success_count = sum(1 for c in results if c.context_text)
        log.info(
            "context.generation.done",
            success=success_count,
            total=len(chunks),
        )
        return list(results)
