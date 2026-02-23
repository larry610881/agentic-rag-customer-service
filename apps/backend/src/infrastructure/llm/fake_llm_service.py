"""FakeLLMService — 確定性回應，用於測試與開發"""

from collections.abc import AsyncIterator

from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import LLMResult, TokenUsage


class FakeLLMService(LLMService):
    """不依賴真實 LLM API 的假實作"""

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> LLMResult:
        if not context or not context.strip():
            text = "知識庫中沒有找到相關資訊，請嘗試其他問題。"
        else:
            snippet = context[:200]
            text = f"根據知識庫：{snippet}"
        return LLMResult(text=text, usage=TokenUsage.zero("fake"))

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> AsyncIterator[str]:
        result = await self.generate(system_prompt, user_message, context)
        for char in result.text:
            yield char
