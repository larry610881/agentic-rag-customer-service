from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


@dataclass
class FailedCase:
    case_id: str
    question: str
    actual_answer: str
    failed_assertions: list[str]  # assertion type names that failed


@dataclass
class CostStats:
    avg_input_tokens: int = 0
    avg_output_tokens: int = 0
    avg_cost: float = 0.0
    prompt_tokens: int = 0  # system prompt token count estimate
    token_budget: int = 2000


class PromptMutator:
    """Uses an LLM to generate improved prompt variants based on failed test cases."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self._model_name = model

    async def mutate(
        self,
        current_prompt: str,
        failed_cases: list[FailedCase],
        iteration: int,
        cost_stats: CostStats | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate a mutated prompt that addresses failed cases.

        Temperature escalation: if called with higher temperature on stagnation,
        the caller (runner) manages this by passing increased temperature.
        """
        meta_prompt = self._build_meta_prompt(
            current_prompt, failed_cases, cost_stats, iteration
        )

        llm = ChatOpenAI(
            model=self._model_name,
            temperature=temperature,
        )

        # Retry up to 3 times if LLM returns empty or identical prompt
        for attempt in range(3):
            response = await llm.ainvoke([HumanMessage(content=meta_prompt)])
            candidate = response.content.strip()

            if candidate and candidate != current_prompt:
                logger.info(
                    "Mutation succeeded (iteration=%d, attempt=%d, len=%d→%d)",
                    iteration,
                    attempt + 1,
                    len(current_prompt),
                    len(candidate),
                )
                return candidate

            # Increase temperature for retry
            temperature = min(temperature + 0.2, 1.5)
            llm = ChatOpenAI(model=self._model_name, temperature=temperature)
            logger.warning("Mutation retry %d (empty or identical)", attempt + 1)

        # If all retries fail, return original with minor modification hint
        logger.error("All mutation attempts failed, returning original prompt")
        return current_prompt

    def _build_meta_prompt(
        self,
        current_prompt: str,
        failed_cases: list[FailedCase],
        cost_stats: CostStats | None,
        iteration: int,
    ) -> str:
        parts = [
            "你是 Prompt 工程專家。改進以下系統提示詞，使其在測試案例中表現更好。",
            "",
            "## 當前提示詞",
            current_prompt,
            "",
            "## 失敗的測試案例",
        ]

        for case in failed_cases[:10]:  # Limit to top 10 to avoid token overflow
            parts.append(f"\n### Case: {case.case_id}")
            parts.append(f"問題：{case.question}")
            parts.append(
                f"實際回答：{case.actual_answer[:300]}..."
            )  # Truncate long answers
            parts.append(f"失敗的檢查：{', '.join(case.failed_assertions)}")

        if cost_stats:
            parts.extend(
                [
                    "",
                    "## 成本統計",
                    f"- 平均 input tokens: {cost_stats.avg_input_tokens}"
                    f" (其中 system prompt 佔 ~{cost_stats.prompt_tokens})",
                    f"- 平均 output tokens: {cost_stats.avg_output_tokens}",
                    f"- 平均單次成本: ${cost_stats.avg_cost:.4f}",
                    f"- Token 預算上限: {cost_stats.token_budget}/次",
                ]
            )

        parts.extend(
            [
                "",
                "## 約束",
                "- 保持核心意圖不變",
                "- 不要增加超過原文 50% 的長度",
                "- 繁體中文",
                "- 不要把測試案例的具體內容寫進提示詞（避免 overfitting）",
                "- 在不損失品質的前提下，盡量精簡指令、減少冗餘",
                "- 如果 output tokens 過高，考慮加入「簡潔回答」指令",
                "",
                f"這是第 {iteration} 輪優化。直接輸出改進後的完整提示詞，不要加任何解釋或標記。",
            ]
        )

        return "\n".join(parts)
