"""Contextual Retrieval: generate document context per chunk using LLM.

Anthropic's research shows this improves retrieval accuracy by ~35%.
Supports any provider via call_llm (Anthropic, OpenAI, LiteLLM, etc.).
"""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

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

    async def generate_contexts(
        self,
        document_content: str,
        chunks: list[Chunk],
        model: str = "",
    ) -> list[Chunk]:
        if not chunks or not document_content.strip():
            return chunks

        model = model or DEFAULT_MODEL
        doc_text = document_content[:MAX_DOC_CHARS]

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        log = logger.bind(model=model, chunk_count=len(chunks))
        log.info("context.generation.start")

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
                        api_key_resolver=self._api_key_resolver,
                    )
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
