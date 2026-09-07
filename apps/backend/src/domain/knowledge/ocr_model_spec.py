"""OCR 模型 spec（``provider:model``）的純函式規則（Issue #78）。

- 支援的供應商：anthropic（Claude Vision）與 google / openai / openrouter / litellm
  （OpenAI 相容視覺端點）。
- 無 ``provider:`` 前綴一律視為 anthropic（沿用 llm_caller 既有慣例）。
- 空字串代表「未設定，沿用上層預設」，永遠合法。
"""

from __future__ import annotations

from src.domain.shared.exceptions import ValidationError

ANTHROPIC_PROVIDER = "anthropic"
OPENAI_COMPAT_OCR_PROVIDERS: frozenset[str] = frozenset(
    {"google", "openai", "openrouter", "litellm"}
)
SUPPORTED_OCR_PROVIDERS: frozenset[str] = frozenset(
    {ANTHROPIC_PROVIDER, *OPENAI_COMPAT_OCR_PROVIDERS}
)


def parse_ocr_model_spec(spec: str) -> tuple[str, str]:
    """``provider:model`` → ``(provider, model)``；無前綴視為 anthropic。"""
    raw = (spec or "").strip()
    if ":" in raw:
        provider, model = raw.split(":", 1)
        return provider.strip().lower(), model.strip()
    return ANTHROPIC_PROVIDER, raw


def normalize_ocr_model_spec(spec: str) -> str:
    """回傳正規化的 ``provider:model``；空字串維持空字串。"""
    if not (spec or "").strip():
        return ""
    provider, model = parse_ocr_model_spec(spec)
    return f"{provider}:{model}"


def validate_ocr_model_spec(spec: str) -> str:
    """驗證並正規化 spec；供應商不支援或 model 為空 → ``ValidationError``。"""
    normalized = normalize_ocr_model_spec(spec)
    if not normalized:
        return ""
    provider, model = parse_ocr_model_spec(normalized)
    if provider not in SUPPORTED_OCR_PROVIDERS:
        raise ValidationError(
            f"OCR 不支援供應商 '{provider}'，"
            f"可用：{', '.join(sorted(SUPPORTED_OCR_PROVIDERS))}"
        )
    if not model:
        raise ValidationError("OCR 模型 spec 缺少 model（格式 provider:model）")
    return normalized
