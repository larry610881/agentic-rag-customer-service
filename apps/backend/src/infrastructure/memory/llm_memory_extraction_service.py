"""LLM-based memory extraction service — 從對話中萃取用戶事實"""

import json

import structlog

from src.domain.memory.entity import MemoryFact
from src.domain.memory.services import ExtractedFact, MemoryExtractionService
from src.domain.rag.services import LLMService

logger = structlog.get_logger(__name__)

DEFAULT_EXTRACTION_PROMPT = """\
你是記憶萃取助手。分析以下對話，萃取需要記住的用戶資訊。

萃取類別：
- personal_info: 姓名、聯絡偏好、語言偏好
- preference: 產品偏好、配送偏好、溝通風格
- past_issue: 過去問題、投訴、已解決事項
- purchase: 提到的產品、訂單
- sentiment: 客戶整體情緒

每個事實提供：
- category: 上述類別之一
- key: 簡短描述（如 "偏好配送方式"）
- value: 萃取的資訊（如 "冷凍配送"）
- confidence: 0.0-1.0

已知事實（不重複，但有新資訊可更新）：
{existing_facts}

對話：
{conversation}

回傳 JSON 陣列。無新事實則回傳 []。"""


class LLMMemoryExtractionService(MemoryExtractionService):
    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def extract_facts(
        self,
        conversation_messages: list[dict[str, str]],
        existing_facts: list[MemoryFact],
        extraction_prompt: str = "",
    ) -> list[ExtractedFact]:
        prompt_template = extraction_prompt or DEFAULT_EXTRACTION_PROMPT

        # Format existing facts
        existing_str = ""
        if existing_facts:
            lines = [f"- {f.key}: {f.value}" for f in existing_facts]
            existing_str = "\n".join(lines)
        else:
            existing_str = "（無已知事實）"

        # Format conversation
        conv_lines = []
        for msg in conversation_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conv_lines.append(f"{role}: {content}")
        conv_str = "\n".join(conv_lines)

        prompt = prompt_template.replace(
            "{existing_facts}", existing_str
        ).replace("{conversation}", conv_str)

        try:
            response = await self._llm.generate(
                prompt=prompt,
                system_prompt="你是記憶萃取助手，只回傳 JSON 陣列。",
            )
            return self._parse_response(response)
        except Exception:
            logger.warning("memory.extraction.llm_failed", exc_info=True)
            return []

    @staticmethod
    def _parse_response(response: str) -> list[ExtractedFact]:
        """Parse LLM response into ExtractedFact list."""
        # Strip markdown code block if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # remove opening ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("memory.extraction.parse_failed", raw=text[:200])
            return []

        if not isinstance(data, list):
            return []

        facts = []
        for item in data:
            if not isinstance(item, dict):
                continue
            key = item.get("key", "").strip()
            value = item.get("value", "").strip()
            if not key or not value:
                continue
            facts.append(
                ExtractedFact(
                    category=item.get("category", "custom"),
                    key=key,
                    value=value,
                    confidence=min(1.0, max(0.0, float(item.get("confidence", 1.0)))),
                )
            )
        return facts
