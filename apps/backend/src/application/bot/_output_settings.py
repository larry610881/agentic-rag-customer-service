"""Bot 模式 / 輸出格式欄位驗證（Create / Update 共用，Issue #70）"""

from __future__ import annotations

from typing import Any

from src.domain.bot.entity import VALID_BOT_MODES, VALID_OUTPUT_FORMATS
from src.domain.llm.structured_output import validate_json_output
from src.domain.shared.exceptions import ValidationError

_MAX_TEXT_FIELD_LEN = 64


def validate_output_settings(
    *,
    mode: Any,
    output_format: Any,
    output_schema: Any,
    miss_reply: Any,
    output_text_field: Any,
) -> None:
    if mode not in VALID_BOT_MODES:
        raise ValidationError(f"mode must be one of {list(VALID_BOT_MODES)}")
    if output_format not in VALID_OUTPUT_FORMATS:
        raise ValidationError(
            f"output_format must be one of {list(VALID_OUTPUT_FORMATS)}"
        )
    if (
        not isinstance(output_text_field, str)
        or not output_text_field.strip()
        or len(output_text_field) > _MAX_TEXT_FIELD_LEN
    ):
        raise ValidationError(
            "output_text_field must be a non-empty string "
            f"(≤ {_MAX_TEXT_FIELD_LEN} chars)"
        )
    if output_format != "json":
        return
    if output_schema is not None:
        if not isinstance(output_schema, dict):
            raise ValidationError("output_schema must be a JSON schema object")
        try:
            import jsonschema

            jsonschema.Draft202012Validator.check_schema(output_schema)
        except Exception as exc:
            raise ValidationError(
                f"output_schema is not a valid JSON schema: {exc}"
            ) from exc
    if miss_reply:
        ok, _, error = validate_json_output(str(miss_reply), output_schema)
        if not ok:
            raise ValidationError(
                f"miss_reply must be a JSON object matching output_schema when "
                f"output_format is json: {error}"
            )
