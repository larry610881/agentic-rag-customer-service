"""RAG Quality Diagnostic Engine — 根據評估維度分數產生改善提示。

純 rule-based，無需額外 LLM call。On-the-fly 計算，不存 DB。
"""

from dataclasses import dataclass


@dataclass
class DiagnosticHint:
    category: str    # "data_source" | "rag_strategy" | "prompt" | "agent"
    severity: str    # "critical" | "warning" | "info"
    dimension: str   # 觸發的維度名稱
    message: str     # 人類可讀的診斷描述
    suggestion: str  # 改善建議


# -----------------------------------------------------------------------
# Single-dimension rules: (dim, threshold, category, severity, msg, sug)
# -----------------------------------------------------------------------
_SINGLE_RULES: list[tuple[str, float, str, str, str, str]] = [
    (
        "context_precision", 0.3, "data_source", "critical",
        "檢索結果與問題幾乎無關，可能是知識庫缺少相關資料",
        "檢查知識庫是否包含相關文件，必要時補充資料源",
    ),
    (
        "context_precision", 0.5, "rag_strategy", "warning",
        "檢索精確度偏低，考慮調整 chunk 大小或 embedding 模型",
        "嘗試縮小 chunk size、更換 embedding 模型、或啟用 re-ranking",
    ),
    (
        "context_recall", 0.3, "data_source", "critical",
        "知識庫可能缺少完整回答所需的資訊",
        "補充知識庫資料，確保涵蓋常見問題的完整資訊",
    ),
    (
        "context_recall", 0.5, "rag_strategy", "warning",
        "資訊覆蓋不足，考慮增加 top_k 或啟用 re-ranking",
        "增加 top_k 檢索數量或啟用 re-ranking 提升召回率",
    ),
    (
        "faithfulness", 0.3, "prompt", "critical",
        "回答嚴重偏離上下文，模型產生大量幻覺",
        "強化 System Prompt 中的 grounding 約束，要求模型只基於上下文回答",
    ),
    (
        "faithfulness", 0.5, "prompt", "warning",
        "部分回答未基於上下文，考慮強化 System Prompt 約束",
        "在 Prompt 中加入「僅根據提供的資料回答」等明確指示",
    ),
    (
        "relevancy", 0.3, "prompt", "critical",
        "回答完全偏題，檢查 Prompt 是否有效引導模型",
        "重新審視 System Prompt，確保清楚定義回答範圍與角色",
    ),
    (
        "relevancy", 0.5, "prompt", "warning",
        "回答相關性不足，考慮調整 Prompt 或增加 few-shot",
        "嘗試加入 few-shot 範例或調整 query rewrite 策略",
    ),
    (
        "agent_efficiency", 0.3, "agent", "critical",
        "Agent 決策效率極低，迴圈過多或重複查詢",
        "檢查 Agent 的 max_iterations 設定，並審視 Tool 描述是否造成混淆",
    ),
    (
        "tool_selection", 0.3, "agent", "warning",
        "工具選擇不當，檢查 Tool 描述是否清晰",
        "改善 Tool 的 description，讓 Agent 能更準確判斷何時使用哪個工具",
    ),
]


def _get_score(dimensions: list[dict], name: str) -> float | None:
    """取得指定維度的分數，不存在則回傳 None。"""
    for d in dimensions:
        if d.get("name") == name:
            return float(d.get("score", 0))
    return None


def _apply_single_rules(dimensions: list[dict]) -> list[DiagnosticHint]:
    """套用單一維度門檻規則。"""
    hints: list[DiagnosticHint] = []
    triggered: set[tuple[str, str]] = set()  # (dimension, severity) 去重

    for dim_name, threshold, category, severity, message, suggestion in _SINGLE_RULES:
        score = _get_score(dimensions, dim_name)
        if score is None:
            continue
        if score <= threshold:
            key = (dim_name, severity)
            if key not in triggered:
                triggered.add(key)
                hints.append(DiagnosticHint(
                    category=category,
                    severity=severity,
                    dimension=dim_name,
                    message=message,
                    suggestion=suggestion,
                ))
    return hints


def _apply_combo_rules(dimensions: list[dict]) -> list[DiagnosticHint]:
    """套用跨維度組合規則。"""
    hints: list[DiagnosticHint] = []
    precision = _get_score(dimensions, "context_precision")
    recall = _get_score(dimensions, "context_recall")
    faithfulness = _get_score(dimensions, "faithfulness")
    relevancy = _get_score(dimensions, "relevancy")

    if precision is not None and recall is not None:
        if precision > 0.6 and recall <= 0.3:
            hints.append(DiagnosticHint(
                category="rag_strategy", severity="warning",
                dimension="context_precision+context_recall",
                message="檢索到的內容相關但不完整",
                suggestion="增加 top_k 檢索數量以提升資訊覆蓋率",
            ))
        elif precision <= 0.3 and recall > 0.6:
            hints.append(DiagnosticHint(
                category="rag_strategy", severity="warning",
                dimension="context_precision+context_recall",
                message="檢索涵蓋面廣但雜訊多",
                suggestion="考慮啟用 re-ranking 或提高相似度門檻以過濾低品質結果",
            ))

    if faithfulness is not None and relevancy is not None:
        if faithfulness <= 0.3 and relevancy > 0.6:
            hints.append(DiagnosticHint(
                category="prompt", severity="warning",
                dimension="faithfulness+relevancy",
                message="模型理解問題但編造內容",
                suggestion="強化 grounding prompt，要求模型嚴格基於上下文回答",
            ))
        elif faithfulness > 0.6 and relevancy <= 0.3:
            hints.append(DiagnosticHint(
                category="prompt", severity="warning",
                dimension="faithfulness+relevancy",
                message="模型忠於上下文但答非所問",
                suggestion="檢查 query rewrite 邏輯，確保改寫後的查詢仍反映使用者意圖",
            ))

    return hints


def diagnose(dimensions: list[dict]) -> list[DiagnosticHint]:
    """根據 eval dimensions 的分數模式產生診斷提示。

    Args:
        dimensions: 評估維度列表，每項含 ``name`` 和 ``score``。

    Returns:
        診斷提示列表，可能為空（表示所有分數正常）。
    """
    hints = _apply_single_rules(dimensions)
    hints.extend(_apply_combo_rules(dimensions))
    return hints
