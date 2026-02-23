"""FakeLLMService — 確定性回應，用於測試與開發"""

from collections.abc import AsyncIterator

from src.domain.rag.services import LLMService


class FakeLLMService(LLMService):
    """不依賴真實 LLM API 的假實作"""

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> str:
        if not context or not context.strip():
            return "知識庫中沒有找到相關資訊，請嘗試其他問題。"
        snippet = context[:200]
        return f"根據知識庫：{snippet}"

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> AsyncIterator[str]:
        answer = await self.generate(system_prompt, user_message, context)
        for char in answer:
            yield char
