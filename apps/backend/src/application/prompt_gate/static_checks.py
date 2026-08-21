"""第 0 層同步靜態檢查（毫秒級、免費，spec §4.2）

失敗直接擋、不產生版本、不跑 eval。純函式、無 I/O。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.shared.exceptions import DomainException

# 系統支援的模板變數（對齊 application/agent/prompt_assembler.py）
KNOWN_TEMPLATE_VARS = frozenset({"today", "now", "weekday_zh"})

# 長度上限（字元）：約 17k tokens
MAX_PROMPT_LENGTH = 32_000

# 明顯 injection 句式黑名單（種子清單自 _security_base.yaml 攻擊語料反向提煉）
_INJECTION_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"忽略(以上|之前|前面|所有|上述)的?(所有|全部)?的?(指示|指令|規則|設定)",
        r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?",
        r"disregard\s+(all\s+)?(previous|above|prior)\s+instructions?",
        r"無視(以上|之前|前面|所有|上述)的?(所有|全部)?的?(指示|指令|規則|設定)",
        r"你現在(是|不再是|扮演)",
        r"you\s+are\s+now\s+(a|an|no\s+longer)",
        r"忘(記|掉)(你的|以上|之前|所有)[的]?(指示|指令|規則|設定|身分)",
        r"forget\s+(all\s+)?(your|previous)\s+(instructions?|rules?)",
        r"(顯示|輸出|印出|透露)(你的|完整的?)?(系統提示|system\s*prompt)",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
    )
)

# 模板變數樣式：{var}；{{...}} 為字面大括號（JSON 範例），不視為變數
_TEMPLATE_VAR_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


@dataclass(frozen=True)
class StaticCheckViolation:
    type: str  # unknown_variable | too_long | injection_phrase
    detail: str


@dataclass(frozen=True)
class StaticCheckResult:
    violations: list[StaticCheckViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


class StaticCheckFailedError(DomainException):
    """靜態檢查未通過（interfaces 層對應 400 + 逐項明細）。"""

    def __init__(self, violations: list[StaticCheckViolation]) -> None:
        self.violations = violations
        detail = "; ".join(f"[{v.type}] {v.detail}" for v in violations)
        super().__init__(f"Static prompt checks failed: {detail}")


def check_prompt(text: str) -> StaticCheckResult:
    """對單一 prompt 文字執行全部靜態檢查。空字串合法（= 系統預設）。"""
    violations: list[StaticCheckViolation] = []
    if not text:
        return StaticCheckResult(violations)

    for match in _TEMPLATE_VAR_RE.finditer(text):
        var = match.group(1)
        if var not in KNOWN_TEMPLATE_VARS:
            violations.append(
                StaticCheckViolation(
                    type="unknown_variable",
                    detail=f"未知模板變數 {{{var}}}，"
                    f"僅支援 {sorted(KNOWN_TEMPLATE_VARS)}",
                )
            )

    if len(text) > MAX_PROMPT_LENGTH:
        violations.append(
            StaticCheckViolation(
                type="too_long",
                detail=f"長度 {len(text)} 超過上限 {MAX_PROMPT_LENGTH} 字元",
            )
        )

    for pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            violations.append(
                StaticCheckViolation(
                    type="injection_phrase",
                    detail=f"疑似注入句式：「{m.group(0)}」",
                )
            )

    return StaticCheckResult(violations)


def check_prompt_fields(prompts: dict[str, str]) -> None:
    """檢查多個 prompt 欄位（{欄位名: 文字}），任一違規即 raise。"""
    all_violations: list[StaticCheckViolation] = []
    for field_name, text in prompts.items():
        # M1：非字串值（如 {"bot_prompt": 123}）原本讓 _TEMPLATE_VAR_RE.finditer
        # 拋 TypeError → 未被分類 → 500。改為 StaticCheckViolation → 400。
        if text is not None and not isinstance(text, str):
            all_violations.append(
                StaticCheckViolation(
                    type="invalid_type",
                    detail=f"{field_name}: 必須為字串，收到 {type(text).__name__}",
                )
            )
            continue
        result = check_prompt(text or "")
        for v in result.violations:
            all_violations.append(
                StaticCheckViolation(
                    type=v.type, detail=f"{field_name}: {v.detail}"
                )
            )
    if all_violations:
        raise StaticCheckFailedError(all_violations)
