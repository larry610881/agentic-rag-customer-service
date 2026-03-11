"""RAG Quality Diagnostic Engine — 根據評估維度分數產生改善提示。

純 rule-based，無需額外 LLM call。On-the-fly 計算，不存 DB。
"""

from __future__ import annotations

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

# -----------------------------------------------------------------------
# Combo rules — structured format for DB persistence
# Each combo: {dim_a, op_a, threshold_a, dim_b, op_b, threshold_b,
#              category, severity, dimension_label, message, suggestion}
# -----------------------------------------------------------------------
_COMBO_RULES: list[dict] = [
    {
        "dim_a": "context_precision", "op_a": ">", "threshold_a": 0.6,
        "dim_b": "context_recall", "op_b": "<=", "threshold_b": 0.3,
        "category": "rag_strategy", "severity": "warning",
        "dimension": "context_precision+context_recall",
        "message": "檢索到的內容相關但不完整",
        "suggestion": "增加 top_k 檢索數量以提升資訊覆蓋率",
    },
    {
        "dim_a": "context_precision", "op_a": "<=", "threshold_a": 0.3,
        "dim_b": "context_recall", "op_b": ">", "threshold_b": 0.6,
        "category": "rag_strategy", "severity": "warning",
        "dimension": "context_precision+context_recall",
        "message": "檢索涵蓋面廣但雜訊多",
        "suggestion": "考慮啟用 re-ranking 或提高相似度門檻以過濾低品質結果",
    },
    {
        "dim_a": "faithfulness", "op_a": "<=", "threshold_a": 0.3,
        "dim_b": "relevancy", "op_b": ">", "threshold_b": 0.6,
        "category": "prompt", "severity": "warning",
        "dimension": "faithfulness+relevancy",
        "message": "模型理解問題但編造內容",
        "suggestion": "強化 grounding prompt，要求模型嚴格基於上下文回答",
    },
    {
        "dim_a": "faithfulness", "op_a": ">", "threshold_a": 0.6,
        "dim_b": "relevancy", "op_b": "<=", "threshold_b": 0.3,
        "category": "prompt", "severity": "warning",
        "dimension": "faithfulness+relevancy",
        "message": "模型忠於上下文但答非所問",
        "suggestion": "檢查 query rewrite 邏輯，確保改寫後的查詢仍反映使用者意圖",
    },
]


def get_default_single_rules() -> list[dict]:
    """回傳預設的單維度規則（dict 格式，適合序列化）。"""
    return [
        {
            "dimension": dim, "threshold": thr, "category": cat,
            "severity": sev, "message": msg, "suggestion": sug,
        }
        for dim, thr, cat, sev, msg, sug in _SINGLE_RULES
    ]


def get_default_combo_rules() -> list[dict]:
    """回傳預設的交叉維度規則（dict 格式，適合序列化）。"""
    return [dict(r) for r in _COMBO_RULES]


def _get_score(dimensions: list[dict], name: str) -> float | None:
    """取得指定維度的分數，不存在則回傳 None。"""
    for d in dimensions:
        if d.get("name") == name:
            return float(d.get("score", 0))
    return None


def _compare(score: float, op: str, threshold: float) -> bool:
    """根據運算子比較分數。"""
    if op == "<=":
        return score <= threshold
    if op == "<":
        return score < threshold
    if op == ">=":
        return score >= threshold
    if op == ">":
        return score > threshold
    if op == "==":
        return score == threshold
    return False


def _apply_single_rules(
    dimensions: list[dict],
    rules: list[dict] | None = None,
) -> list[DiagnosticHint]:
    """套用單一維度門檻規則。"""
    if rules is None:
        rules = get_default_single_rules()

    hints: list[DiagnosticHint] = []
    triggered: set[tuple[str, str]] = set()  # (dimension, severity) 去重

    for rule in rules:
        dim_name = rule["dimension"]
        threshold = float(rule["threshold"])
        score = _get_score(dimensions, dim_name)
        if score is None:
            continue
        if score <= threshold:
            key = (dim_name, rule["severity"])
            if key not in triggered:
                triggered.add(key)
                hints.append(DiagnosticHint(
                    category=rule["category"],
                    severity=rule["severity"],
                    dimension=dim_name,
                    message=rule["message"],
                    suggestion=rule["suggestion"],
                ))
    return hints


def _apply_combo_rules(
    dimensions: list[dict],
    rules: list[dict] | None = None,
) -> list[DiagnosticHint]:
    """套用跨維度組合規則。"""
    if rules is None:
        rules = get_default_combo_rules()

    hints: list[DiagnosticHint] = []
    for rule in rules:
        score_a = _get_score(dimensions, rule["dim_a"])
        score_b = _get_score(dimensions, rule["dim_b"])
        if score_a is None or score_b is None:
            continue
        if _compare(score_a, rule["op_a"], float(rule["threshold_a"])) and \
           _compare(score_b, rule["op_b"], float(rule["threshold_b"])):
            hints.append(DiagnosticHint(
                category=rule["category"],
                severity=rule["severity"],
                dimension=rule["dimension"],
                message=rule["message"],
                suggestion=rule["suggestion"],
            ))
    return hints


def diagnose(
    dimensions: list[dict],
    rule_config: object | None = None,
) -> list[DiagnosticHint]:
    """根據 eval dimensions 的分數模式產生診斷提示。

    Args:
        dimensions: 評估維度列表，每項含 ``name`` 和 ``score``。
        rule_config: 可選的 DiagnosticRulesConfig。None 時使用預設規則。

    Returns:
        診斷提示列表，可能為空（表示所有分數正常）。
    """
    single_rules = None
    combo_rules = None
    if rule_config is not None:
        sr = rule_config.single_rules  # type: ignore[union-attr]
        cr = rule_config.combo_rules  # type: ignore[union-attr]
        single_rules = sr if sr is not None else None
        combo_rules = cr if cr is not None else None

    hints = _apply_single_rules(dimensions, single_rules)
    hints.extend(_apply_combo_rules(dimensions, combo_rules))
    return hints
