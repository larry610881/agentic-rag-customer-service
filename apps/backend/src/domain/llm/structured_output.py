"""供應商 × 模型 → JSON 結構化輸出能力等級 + 輸出驗證 / 後處理純函式（Issue #70）

三個等級：
- native_schema：供應商 API 直接吃 JSON schema（OpenAI json_schema response_format、
  Gemini responseSchema、Anthropic output_config.format、Ollama format）
- json_object：只能要求「輸出 JSON 物件」，schema 得寫進 prompt，回來後由我們驗證
- prompt_only：純 prompt 約束 + 事後驗證（聚合器 / 代理 / 未知供應商）

能力表核對日期：2026-09-04（新模型上市請更新此表；前綴比對、不分大小寫）。
本模組為純 Python（domain 層），不得 import 任何框架。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

NATIVE_SCHEMA = "native_schema"
JSON_OBJECT = "json_object"
PROMPT_ONLY = "prompt_only"


class StructuredOutputTier:
    NATIVE_SCHEMA = NATIVE_SCHEMA
    JSON_OBJECT = JSON_OBJECT
    PROMPT_ONLY = PROMPT_ONLY
    ALL = (NATIVE_SCHEMA, JSON_OBJECT, PROMPT_ONLY)


_OPENAI_NATIVE_PREFIXES = ("gpt-4o", "gpt-4.1", "gpt-5", "o1", "o3", "o4")
_GOOGLE_NATIVE_PREFIXES = ("gemini-1.5", "gemini-2", "gemini-3")
_ANTHROPIC_NATIVE_MARKERS = (
    "4-5", "4.5", "opus-4-1", "opus-4.1", "sonnet-5", "opus-5", "haiku-4-5",
)
_ANTHROPIC_VERSION = re.compile(r"claude-(?:opus|sonnet|haiku)-(\d+)(?:[-.](\d+))?")


def _anthropic_native(model: str) -> bool:
    if any(marker in model for marker in _ANTHROPIC_NATIVE_MARKERS):
        return True
    if model.startswith("claude-5"):
        return True
    m = _ANTHROPIC_VERSION.search(model)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2) or 0)
        return major >= 5 or (major == 4 and minor >= 5)
    return False


_VALIDATED_SUFFIX = "schema 寫入 prompt 後由系統驗證（失敗重試一次）"

# provider → (是否原生的判定, 原生說明, 非原生說明)；None 判定 = 固定等級
_CAPABILITY_TABLE: dict[str, tuple[Callable[[str], bool] | None, str, str]] = {
    "openai": (
        lambda m: m.startswith(_OPENAI_NATIVE_PREFIXES),
        "OpenAI json_schema response_format：API 端保證符合 schema",
        "舊版 OpenAI 模型僅支援 json_object，" + _VALIDATED_SUFFIX,
    ),
    "google": (
        lambda m: m.startswith(_GOOGLE_NATIVE_PREFIXES),
        "Gemini 1.5+ 支援 responseSchema：API 端保證符合 schema",
        "此 Gemini 模型僅能要求 JSON 物件，" + _VALIDATED_SUFFIX,
    ),
    "anthropic": (
        _anthropic_native,
        "Claude 4.5+ 支援 output_config.format 原生結構化輸出",
        "舊版 Claude 無原生結構化輸出，以 prompt 約束 + 系統驗證（失敗重試一次）",
    ),
    "deepseek": (
        lambda _m: False,
        "",
        "DeepSeek 支援 json_object，" + _VALIDATED_SUFFIX,
    ),
    "qwen": (
        lambda m: m.startswith("qwen3"),
        "Qwen3 支援 json_schema response_format",
        "此 Qwen 模型僅支援 json_object，" + _VALIDATED_SUFFIX,
    ),
    "ollama": (
        lambda _m: True,
        "Ollama 以 format 參數傳入 schema；實際遵循品質依本地模型而定，系統仍會驗證",
        "",
    ),
}
_CAPABILITY_TABLE["claude"] = _CAPABILITY_TABLE["anthropic"]

_PROMPT_ONLY_NOTE = (
    "此供應商不保證結構化輸出（聚合器 / 代理 / 未知），"
    "僅以 prompt 約束並由系統驗證（失敗重試一次）"
)


def capability(provider: str, model: str) -> tuple[str, str]:
    """回傳 (tier, note)。note 為給前端提示用的一句話說明。"""
    p = (provider or "").strip().lower()
    m = (model or "").strip().lower()
    entry = _CAPABILITY_TABLE.get(p)
    if entry is None:
        # openrouter / litellm / mock / 未知：聚合器與代理不保證透傳 response_format
        return PROMPT_ONLY, _PROMPT_ONLY_NOTE
    is_native, native_note, fallback_note = entry
    if is_native is not None and is_native(m):
        return NATIVE_SCHEMA, native_note
    return JSON_OBJECT, fallback_note


def schema_prompt_block(schema: dict | None) -> str:
    """B / C 級：把 schema 寫進 system prompt 的固定段落。"""
    if not schema:
        return (
            "【輸出格式】必須輸出且只輸出合法 JSON 物件，"
            "不得夾帶任何說明文字或 Markdown。"
        )
    compact = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    return (
        "【輸出格式】必須輸出且只輸出符合以下 JSON schema 的合法 JSON，"
        f"不得夾帶任何說明文字或 Markdown：{compact}"
    )


def is_strict_compatible(schema: Any) -> bool:
    """OpenAI / Gemini strict 模式：每層 object 都 additionalProperties=false
    且 properties 全部列在 required。不符時以 strict=false 送出（仍會事後驗證）。"""
    if not isinstance(schema, dict):
        return False
    return _strict_node(schema)


def _is_object_node(node: dict) -> bool:
    node_type = node.get("type")
    if node_type == "object" or "properties" in node:
        return True
    return isinstance(node_type, list) and "object" in node_type


def _strict_object(node: dict) -> bool:
    props = node.get("properties") or {}
    if node.get("additionalProperties") is not False:
        return False
    return set(node.get("required") or []) == set(props.keys())


def _child_nodes(node: dict) -> list[Any]:
    """需要遞迴檢查的子 schema：properties / items / 組合子 / 定義。"""
    children: list[Any] = list((node.get("properties") or {}).values())
    items = node.get("items")
    children.extend(items if isinstance(items, list) else [items])
    for key in ("anyOf", "oneOf", "allOf"):
        children.extend(node.get(key) or [])
    for key in ("$defs", "definitions"):
        children.extend((node.get(key) or {}).values())
    return children


def _strict_node(node: Any) -> bool:
    if not isinstance(node, dict):
        return True
    if _is_object_node(node) and not _strict_object(node):
        return False
    return all(_strict_node(child) for child in _child_nodes(node))


_FENCE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?|\n?\s*```\s*$")


def strip_code_fences(text: str) -> str:
    return _FENCE.sub("", text or "").strip()


# JSON 字串字面值（含跳脫），用來跳過字串內的大括號
_JSON_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def extract_json_object(text: str) -> str | None:
    """取出文字中第一個括號平衡的 {...} 物件（忽略字串內的括號）。"""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == '"':
            m = _JSON_STRING.match(text, i)
            i = m.end() if m else len(text)
            continue
        depth += (ch == "{") - (ch == "}")
        if depth == 0:
            return text[start : i + 1]
        i += 1
    return None


def validate_json_output(
    text: str, schema: dict | None
) -> tuple[bool, dict | None, str]:
    """剝 ``` 圍欄 → json.loads（失敗則抓第一個平衡 {...} 重試）→ schema 驗證。

    回 (ok, parsed, error)。parsed 只接受 JSON 物件（dict）。
    """
    cleaned = strip_code_fences(text)
    if not cleaned:
        return False, None, "empty output"
    parsed: Any = None
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        candidate = extract_json_object(cleaned)
        if candidate is None:
            return False, None, "output is not valid JSON"
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError) as exc:
            return False, None, f"output is not valid JSON ({exc})"
    if not isinstance(parsed, dict):
        return False, None, "output is not a JSON object"
    if schema:
        try:
            import jsonschema

            validator = jsonschema.Draft202012Validator(schema)
            first = next(iter(validator.iter_errors(parsed)), None)
        except Exception as exc:  # schema 本身壞掉：視為不符（create/update 已擋）
            return False, parsed, f"schema validation unavailable: {exc}"
        if first is not None:
            path = "/".join(str(p) for p in first.absolute_path) or "$"
            return False, parsed, f"schema violation at {path}: {first.message}"
    return True, parsed, ""


# ── plain_text：剝除 Markdown 排版符號，保留內容與換行 ──
_MD_FENCE_LINE = re.compile(r"^[ \t]*```[^\n]*$", re.MULTILINE)
_MD_HEADING = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)
_MD_BLOCKQUOTE = re.compile(r"^[ \t]*>[ \t]?", re.MULTILINE)
_MD_BULLET = re.compile(r"^[ \t]*[-*+][ \t]+", re.MULTILINE)
_MD_ORDERED = re.compile(r"^[ \t]*\d+[.)][ \t]+", re.MULTILINE)
_MD_LINK = re.compile(r"\[([^\]]+)\]\((\S+?)\)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\((\S+?)\)")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.DOTALL)
_MD_ITALIC = re.compile(
    r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])"
    r"|(?<!\w)_(?!\s)([^_\n]+?)(?<!\s)_(?!\w)"
)
_MD_STRIKE = re.compile(r"~~(.+?)~~", re.DOTALL)
_MD_INLINE_CODE = re.compile(r"`([^`\n]*)`")
_MD_TABLE_SEP = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$\n?",
    re.MULTILINE,
)
_MD_HR = re.compile(r"^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$\n?", re.MULTILINE)


def strip_markdown(text: str) -> str:
    """把 Markdown 轉成純文字：標題 / 清單 / 粗斜體 / 行內碼 / 圍欄 / 連結 / 分隔線。
    表格豎線保留為文字（僅移除 |---| 分隔列）；保留換行。"""
    if not text:
        return text
    out = _MD_FENCE_LINE.sub("", text)
    out = _MD_HR.sub("", out)
    out = _MD_TABLE_SEP.sub("", out)
    out = _MD_IMAGE.sub(r"\1", out)
    out = _MD_LINK.sub(r"\1 \2", out)
    out = _MD_HEADING.sub("", out)
    out = _MD_BLOCKQUOTE.sub("", out)
    out = _MD_BULLET.sub("", out)
    out = _MD_ORDERED.sub("", out)
    out = _MD_BOLD.sub(lambda m: m.group(1) or m.group(2) or "", out)
    out = _MD_STRIKE.sub(r"\1", out)
    out = _MD_ITALIC.sub(lambda m: m.group(1) or m.group(2) or "", out)
    out = _MD_INLINE_CODE.sub(r"\1", out)
    return "\n".join(line.rstrip() for line in out.split("\n")).strip("\n")
