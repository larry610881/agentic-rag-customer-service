"""RAG Evaluation Use Case — 多層 RAG 品質評估

使用獨立的 LLM（可與 Bot LLM 不同）進行評估，
支援 3 層深度：L1 (per-RAG call) / L2 (end-to-end) / L3 (agent decisions)
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, ConfigDict, field_validator

from src.domain.observability.evaluation import EvalDimension, EvalResult
from src.domain.observability.trace_record import RAGTraceRecord
from src.domain.rag.services import LLMService

logger = structlog.get_logger(__name__)


# ── Pydantic models for _parse_scores validation ──


class ChunkScoreItem(BaseModel):
    index: int = 0
    score: float = 0.0
    reason: str = ""
    # QualityEdit.1 P0: 跳轉到 KB Studio 編輯這個 chunk 用
    chunk_id: str | None = None
    kb_id: str | None = None

    @field_validator("score", mode="before")
    @classmethod
    def normalize_score(cls, v: object) -> float:
        if isinstance(v, str):
            v = v.replace("%", "").strip()
        val = float(v)  # type: ignore[arg-type]
        return round(val / 100.0, 4) if val > 1.0 else round(val, 4)


class DimensionScore(BaseModel):
    score: float = 0.0
    explanation: str = ""


class EvalScores(BaseModel):
    context_precision: float | DimensionScore = 0.0
    context_recall: float | DimensionScore = 0.0
    faithfulness: float | DimensionScore = 0.0
    relevancy: float | DimensionScore = 0.0
    agent_efficiency: float | DimensionScore = 0.0
    tool_selection: float | DimensionScore = 0.0
    chunk_scores: list[ChunkScoreItem] = []
    explanation: str = ""
    model_config = ConfigDict(extra="ignore")

# Evaluation prompts
_L1_PROMPT = (
    "你是一個 RAG 品質評估專家。請評估以下查詢和檢索結果的品質。\n\n"
    "查詢：{query}\n\n"
    "檢索到的內容（依序編號）：\n{chunks}\n\n"
    "請分別評估：\n"
    "1. context_precision (0-1): 檢索結果與查詢的整體相關程度\n"
    "2. context_recall (0-1): 檢索結果是否涵蓋回答所需的所有資訊\n"
    "3. chunk_scores: 逐條 chunk 相關性評分\n\n"
    "回傳 JSON 格式：\n"
    '{{"context_precision": 0.8, "context_recall": 0.7, '
    '"chunk_scores": [{{"index": 0, "score": 0.9, "reason": "高度相關"}}], '
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
        chunks_text = (
            "\n---\n".join(f"[{i}] {c}" for i, c in enumerate(chunks))
            if chunks
            else "(無檢索結果)"
        )
        prompt = _L1_PROMPT.format(query=query, chunks=chunks_text)

        try:
            result = await self._llm_service.generate(
                "你是 RAG 品質評估專家", prompt, ""
            )
            scores = self._parse_scores(result.text)
            chunk_scores = scores.get("chunk_scores")
            dimensions = [
                EvalDimension(
                    name="context_precision",
                    score=scores.get("context_precision", 0.0),
                    explanation=scores.get("explanation", ""),
                    metadata={"chunk_scores": chunk_scores} if chunk_scores else None,
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
        agent_mode: str = "react",
        tenant_id: str = "",
        trace_id: str | None = None,
        message_id: str | None = None,
        # QualityEdit.1 P0: chunk_id / kb_id 對齊 chunks index
        # （前 N 筆為 RAG sources，後為 MCP tool outputs）
        chunk_ids: list[str] | None = None,
        chunk_kb_ids: list[str] | None = None,
    ) -> EvalResult:
        """合併評估 — 動態組裝 prompt，1 次 LLM call 完成所有層級。

        根據 has_rag_sources 智慧跳過 L1（MCP-only 無 RAG 檢索語義），
        根據 agent_mode 決定是否包含 L3。
        """
        actual_l1 = run_l1 and has_rag_sources
        actual_l3 = run_l3 and agent_mode == "react"

        sections, expected_keys = self._build_eval_sections(
            actual_l1=actual_l1,
            run_l2=run_l2,
            actual_l3=actual_l3,
            query=query,
            chunks=chunks,
            all_context=all_context,
            answer=answer,
            tool_calls=tool_calls,
        )

        if not expected_keys:
            return EvalResult(
                message_id=message_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
                layer="none",
                dimensions=[],
                model_used=getattr(self._llm_service, "model_name", "unknown"),
            )

        prompt = (
            f"你是一個 RAG 品質評估專家。請評估以下查詢的品質。\n\n"
            f"用戶查詢：{query}\n\n"
            + "\n\n".join(sections)
            + "\n\n回傳 JSON 格式，每個維度用物件包含 score 和 explanation：\n"
            + "範例：{"
            + ", ".join(
                f'"{k}": {{"score": 0.8, "explanation": "針對 {k} 的說明"}}'
                for k in expected_keys
            )
            + "}"
        )

        layer_label = self._determine_layer_label(actual_l1, run_l2, actual_l3)

        try:
            result = await self._llm_service.generate(
                "你是 RAG 品質評估專家", prompt, ""
            )
            scores = self._parse_scores(result.text)
            # QualityEdit.1 P0: 把 chunk_id / kb_id 按 index 對齊塞進 chunk_scores
            _enriched = scores.get("chunk_scores")
            if _enriched and (chunk_ids or chunk_kb_ids):
                for item in _enriched:
                    idx = item.get("index")
                    if isinstance(idx, int) and idx >= 0:
                        if chunk_ids and idx < len(chunk_ids):
                            item["chunk_id"] = chunk_ids[idx]
                        if chunk_kb_ids and idx < len(chunk_kb_ids):
                            item["kb_id"] = chunk_kb_ids[idx]
            dimensions = self._extract_dimensions(scores, expected_keys)
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
    def _build_eval_sections(
        *,
        actual_l1: bool,
        run_l2: bool,
        actual_l3: bool,
        query: str,
        chunks: list[str],
        all_context: str,
        answer: str,
        tool_calls: list[dict],
    ) -> tuple[list[str], list[str]]:
        """Build prompt sections and expected keys for combined eval."""
        sections: list[str] = []
        expected_keys: list[str] = []

        if actual_l1:
            chunks_text = (
                "\n---\n".join(f"[{i}] {c}" for i, c in enumerate(chunks))
                if chunks
                else "(無檢索結果)"
            )
            sections.append(
                f"## L1 檢索品質\n檢索到的內容（依序編號）：\n{chunks_text}\n\n"
                "請評估：\n"
                "- context_precision (0-1): 檢索結果與查詢的整體相關程度\n"
                "- context_recall (0-1): 檢索結果是否涵蓋回答所需的所有資訊\n"
                "- chunk_scores: 逐條 chunk 相關性，格式 "
                '[{"index": 0, "score": 0.9, "reason": "..."}]'
            )
            expected_keys.extend(["context_precision", "context_recall"])

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

        return sections, expected_keys

    @staticmethod
    def _determine_layer_label(
        actual_l1: bool, run_l2: bool, actual_l3: bool,
    ) -> str:
        """Compute layer label like 'L1+L2'."""
        layers = []
        if actual_l1:
            layers.append("L1")
        if run_l2:
            layers.append("L2")
        if actual_l3:
            layers.append("L3")
        return "+".join(layers)

    @staticmethod
    def _extract_dimensions(
        scores: dict, expected_keys: list[str],
    ) -> list[EvalDimension]:
        """Extract EvalDimension list from parsed scores.

        QualityEdit.1 P0: chunk_id/kb_id 已由 _enrich_chunk_scores() 回填，
        直接讀出透傳即可。
        """
        chunk_scores = scores.get("chunk_scores")
        dimensions = []
        for key in expected_keys:
            meta = None
            if key == "context_precision" and chunk_scores:
                meta = {"chunk_scores": chunk_scores}
            dim_val = scores.get(key, 0.0)
            if isinstance(dim_val, dict):
                dim_score = float(dim_val.get("score", 0.0))
                dim_expl = dim_val.get("explanation", "")
            else:
                dim_score = float(dim_val) if dim_val else 0.0
                dim_expl = scores.get("explanation", "")
            dimensions.append(
                EvalDimension(
                    name=key,
                    score=dim_score,
                    explanation=dim_expl,
                    metadata=meta,
                )
            )
        return dimensions

    @staticmethod
    def _parse_scores(text: str) -> dict:
        """Parse JSON scores from LLM response with Pydantic validation."""
        import json
        import re

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```\w*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return {}

        try:
            parsed = EvalScores.model_validate(data)
            return parsed.model_dump()
        except Exception:
            # Fallback: return raw data with basic chunk_scores normalization
            if "chunk_scores" in data and isinstance(data["chunk_scores"], list):
                for cs in data["chunk_scores"]:
                    if isinstance(cs, dict) and "score" in cs:
                        raw = cs["score"]
                        if isinstance(raw, str):
                            raw = raw.replace("%", "").strip()
                        try:
                            val = float(raw)
                            if val > 1.0:
                                val = val / 100.0
                            cs["score"] = round(val, 4)
                        except (ValueError, TypeError):
                            cs["score"] = 0.0
            return data
