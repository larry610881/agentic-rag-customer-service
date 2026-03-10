"""RAG Evaluation Use Case — 多層 RAG 品質評估

使用獨立的 LLM（可與 Bot LLM 不同）進行評估，
支援 3 層深度：L1 (per-RAG call) / L2 (end-to-end) / L3 (agent decisions)
"""

import structlog

from src.domain.observability.evaluation import EvalDimension, EvalResult
from src.domain.observability.trace_record import RAGTraceRecord
from src.domain.rag.services import LLMService

logger = structlog.get_logger(__name__)

# Evaluation prompts
_L1_PROMPT = (
    "你是一個 RAG 品質評估專家。請評估以下查詢和檢索結果的品質。\n\n"
    "查詢：{query}\n\n"
    "檢索到的內容：\n{chunks}\n\n"
    "請分別評估：\n"
    "1. context_precision (0-1): 檢索結果與查詢的相關程度\n"
    "2. context_recall (0-1): 檢索結果是否涵蓋回答所需的所有資訊\n\n"
    "回傳 JSON 格式：\n"
    '{{"context_precision": 0.8, "context_recall": 0.7, '
    '"explanation": "簡短說明"}}'
)

_L2_PROMPT = (
    "你是一個回答品質評估專家。請評估以下最終回答的品質。\n\n"
    "問題：{query}\n\n"
    "使用的上下文：\n{context}\n\n"
    "最終回答：\n{answer}\n\n"
    "請分別評估：\n"
    "1. faithfulness (0-1): 回答是否忠於提供的上下文，沒有幻覺\n"
    "2. relevancy (0-1): 回答是否切中用戶問題\n\n"
    "回傳 JSON 格式：\n"
    '{{"faithfulness": 0.9, "relevancy": 0.85, '
    '"explanation": "簡短說明"}}'
)

_L3_PROMPT = (
    "你是一個 AI Agent 決策品質評估專家。請評估以下 ReAct Agent 的決策過程。\n\n"
    "用戶問題：{query}\n\n"
    "Agent 決策過程：\n{decisions}\n\n"
    "請評估：\n"
    "1. agent_efficiency (0-1): 迴圈次數是否合理，有無重複查詢\n"
    "2. tool_selection (0-1): 工具選擇是否恰當\n\n"
    "回傳 JSON 格式：\n"
    '{{"agent_efficiency": 0.8, "tool_selection": 0.9, '
    '"explanation": "簡短說明"}}'
)


class RAGEvaluationUseCase:
    """RAG 品質評估用例"""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm_service = llm_service

    async def evaluate_l1(
        self,
        query: str,
        chunks: list[str],
        tenant_id: str = "",
        trace_id: str | None = None,
        message_id: str | None = None,
    ) -> EvalResult:
        """L1 評估：單次 RAG 呼叫的 Context Precision/Recall"""
        chunks_text = "\n---\n".join(chunks) if chunks else "(無檢索結果)"
        prompt = _L1_PROMPT.format(query=query, chunks=chunks_text)

        try:
            result = await self._llm_service.generate(
                "你是 RAG 品質評估專家", prompt, ""
            )
            scores = self._parse_scores(result.text)
            dimensions = [
                EvalDimension(
                    name="context_precision",
                    score=scores.get("context_precision", 0.0),
                    explanation=scores.get("explanation", ""),
                ),
                EvalDimension(
                    name="context_recall",
                    score=scores.get("context_recall", 0.0),
                    explanation=scores.get("explanation", ""),
                ),
            ]
        except Exception as exc:
            logger.warning("eval.l1.failed", error=str(exc))
            dimensions = [
                EvalDimension(name="context_precision", score=0.0, explanation=f"評估失敗: {exc}"),
                EvalDimension(name="context_recall", score=0.0, explanation=f"評估失敗: {exc}"),
            ]

        return EvalResult(
            message_id=message_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            layer="L1",
            dimensions=dimensions,
            model_used=getattr(self._llm_service, "model_name", "unknown"),
        )

    async def evaluate_l2(
        self,
        query: str,
        answer: str,
        all_context: str,
        tenant_id: str = "",
        message_id: str | None = None,
    ) -> EvalResult:
        """L2 評估：端到端 Faithfulness/Relevancy"""
        prompt = _L2_PROMPT.format(
            query=query, context=all_context or "(無上下文)", answer=answer
        )

        try:
            result = await self._llm_service.generate(
                "你是回答品質評估專家", prompt, ""
            )
            scores = self._parse_scores(result.text)
            dimensions = [
                EvalDimension(
                    name="faithfulness",
                    score=scores.get("faithfulness", 0.0),
                    explanation=scores.get("explanation", ""),
                ),
                EvalDimension(
                    name="relevancy",
                    score=scores.get("relevancy", 0.0),
                    explanation=scores.get("explanation", ""),
                ),
            ]
        except Exception as exc:
            logger.warning("eval.l2.failed", error=str(exc))
            dimensions = [
                EvalDimension(name="faithfulness", score=0.0, explanation=f"評估失敗: {exc}"),
                EvalDimension(name="relevancy", score=0.0, explanation=f"評估失敗: {exc}"),
            ]

        return EvalResult(
            message_id=message_id,
            tenant_id=tenant_id,
            layer="L2",
            dimensions=dimensions,
            model_used=getattr(self._llm_service, "model_name", "unknown"),
        )

    async def evaluate_l3(
        self,
        query: str,
        tool_calls: list[dict],
        trace_records: list[RAGTraceRecord] | None = None,
        tenant_id: str = "",
        message_id: str | None = None,
    ) -> EvalResult:
        """L3 評估：Agent 決策合理性（僅 ReAct 模式）"""
        decisions = "\n".join([
            f"- 工具: {tc.get('tool_name', 'unknown')}, "
            f"輸入: {tc.get('tool_input', 'N/A')}"
            for tc in tool_calls
        ])
        rag_call_count = len(trace_records) if trace_records else len(tool_calls)
        decisions += f"\n\n總 RAG 呼叫次數: {rag_call_count}"

        prompt = _L3_PROMPT.format(query=query, decisions=decisions)

        try:
            result = await self._llm_service.generate(
                "你是 Agent 決策評估專家", prompt, ""
            )
            scores = self._parse_scores(result.text)
            dimensions = [
                EvalDimension(
                    name="agent_efficiency",
                    score=scores.get("agent_efficiency", 0.0),
                    explanation=scores.get("explanation", ""),
                ),
                EvalDimension(
                    name="tool_selection",
                    score=scores.get("tool_selection", 0.0),
                    explanation=scores.get("explanation", ""),
                ),
            ]
        except Exception as exc:
            logger.warning("eval.l3.failed", error=str(exc))
            dimensions = [
                EvalDimension(name="agent_efficiency", score=0.0, explanation=f"評估失敗: {exc}"),
                EvalDimension(name="tool_selection", score=0.0, explanation=f"評估失敗: {exc}"),
            ]

        return EvalResult(
            message_id=message_id,
            tenant_id=tenant_id,
            layer="L3",
            dimensions=dimensions,
            model_used=getattr(self._llm_service, "model_name", "unknown"),
        )

    async def evaluate_combined(
        self,
        query: str,
        answer: str,
        all_context: str,
        chunks: list[str],
        tool_calls: list[dict],
        *,
        run_l1: bool = False,
        run_l2: bool = False,
        run_l3: bool = False,
        has_rag_sources: bool = False,
        agent_mode: str = "router",
        tenant_id: str = "",
        trace_id: str | None = None,
        message_id: str | None = None,
    ) -> EvalResult:
        """合併評估 — 動態組裝 prompt，1 次 LLM call 完成所有層級。

        根據 has_rag_sources 智慧跳過 L1（MCP-only 無 RAG 檢索語義），
        根據 agent_mode 決定是否包含 L3。
        """
        # Determine actual dimensions to evaluate
        actual_l1 = run_l1 and has_rag_sources
        actual_l3 = run_l3 and agent_mode == "react"

        sections: list[str] = []
        expected_keys: list[str] = []

        # L1 section
        if actual_l1:
            chunks_text = "\n---\n".join(chunks) if chunks else "(無檢索結果)"
            sections.append(
                f"## L1 檢索品質\n檢索到的內容：\n{chunks_text}\n\n"
                "請評估：\n"
                "- context_precision (0-1): 檢索結果與查詢的相關程度\n"
                "- context_recall (0-1): 檢索結果是否涵蓋回答所需的所有資訊"
            )
            expected_keys.extend(["context_precision", "context_recall"])

        # L2 section
        if run_l2:
            ctx = all_context or "(無上下文)"
            sections.append(
                f"## L2 回答品質\n使用的上下文：\n{ctx}\n\n"
                f"最終回答：\n{answer}\n\n"
                "請評估：\n"
                "- faithfulness (0-1): 回答是否忠於提供的上下文，沒有幻覺\n"
                "- relevancy (0-1): 回答是否切中用戶問題"
            )
            expected_keys.extend(["faithfulness", "relevancy"])

        # L3 section
        if actual_l3:
            decisions = "\n".join([
                f"- 工具: {tc.get('tool_name', 'unknown')}, "
                f"輸入: {tc.get('tool_input', 'N/A')}"
                for tc in tool_calls
            ])
            sections.append(
                f"## L3 Agent 決策\nAgent 決策過程：\n{decisions}\n\n"
                "請評估：\n"
                "- agent_efficiency (0-1): 迴圈次數是否合理，有無重複查詢\n"
                "- tool_selection (0-1): 工具選擇是否恰當"
            )
            expected_keys.extend(["agent_efficiency", "tool_selection"])

        if not expected_keys:
            return EvalResult(
                message_id=message_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
                layer="none",
                dimensions=[],
                model_used=getattr(self._llm_service, "model_name", "unknown"),
            )

        # Assemble single prompt
        prompt = (
            f"你是一個 RAG 品質評估專家。請評估以下查詢的品質。\n\n"
            f"用戶查詢：{query}\n\n"
            + "\n\n".join(sections)
            + "\n\n回傳 JSON 格式，包含以下 key：\n"
            + ", ".join(expected_keys)
            + ', explanation\n'
            + "範例：{"
            + ", ".join(f'"{k}": 0.8' for k in expected_keys)
            + ', "explanation": "簡短說明"}'
        )

        # Determine layer label
        layers = []
        if actual_l1:
            layers.append("L1")
        if run_l2:
            layers.append("L2")
        if actual_l3:
            layers.append("L3")
        layer_label = "+".join(layers)

        try:
            result = await self._llm_service.generate(
                "你是 RAG 品質評估專家", prompt, ""
            )
            scores = self._parse_scores(result.text)
            dimensions = [
                EvalDimension(
                    name=key,
                    score=scores.get(key, 0.0),
                    explanation=scores.get("explanation", ""),
                )
                for key in expected_keys
            ]
        except Exception as exc:
            logger.warning("eval.combined.failed", error=str(exc))
            dimensions = [
                EvalDimension(name=key, score=0.0, explanation=f"評估失敗: {exc}")
                for key in expected_keys
            ]

        return EvalResult(
            message_id=message_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            layer=layer_label,
            dimensions=dimensions,
            model_used=getattr(self._llm_service, "model_name", "unknown"),
        )

    @staticmethod
    def _parse_scores(text: str) -> dict:
        """Parse JSON scores from LLM response."""
        import json
        import re

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```\w*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {}
