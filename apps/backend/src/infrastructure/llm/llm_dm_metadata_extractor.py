"""LLM DM Metadata Extractor — Anthropic tool use + Pydantic schema.

Issue #47 L3.3：從 KB 的 cover / promotion 頁 OCR 內容抽出整本 DM 共通的
結構化 metadata（DM 期間 / 商家 / 跨頁活動 / 會員條件 / 主打商品摘要）。

設計重點：
- 用 Pydantic 定義 schema（``DMMetadata``）→ Pydantic ``model_json_schema()``
  → Anthropic ``tools[].input_schema`` → ``tool_choice`` 強制 LLM 吐 schema-
  validated JSON（取代純 prompt + ``json.loads(...)`` 容易吐錯的脆弱模式）
- 未來新增 metadata field 只動 ``DMMetadata`` Pydantic class，**prompt 不動**
- 可靠性大幅提升：合法 JSON 永遠可解析，不用 retry / strip fence

Token tracking 與 ``LLMChunkContextService`` 對齊（5 個屬性），便於 caller
寫 ``record_usage``。
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from src.domain.knowledge.services import DMMetadataExtractor
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
TOOL_NAME = "save_dm_metadata"
MAX_OCR_CHARS = 60_000  # ~15K tokens；單次 LLM 呼叫合理上限
MAX_OUTPUT_TOKENS = 2048


# ── Pydantic schema ──────────────────────────────────────────────


class GlobalActivity(BaseModel):
    name: str = Field(
        description="活動名稱，如「天天生鮮日」「週二/週日加油日」「週四豆米漿日」"
    )
    condition: str = Field(
        description=(
            "完整優惠條件，含金額/百分比/限制（如「刷卡金額 10% 折價券」"
            "「滿 1200 元享 50 元加油折價券」）"
        )
    )


class MemberCondition(BaseModel):
    audience: str = Field(
        description=(
            "會員 / 持卡人類型，如「unipen 聯名卡持卡人」「家樂福 App 會員」"
            "「新會員首購」"
        )
    )
    benefit: str = Field(
        description="優惠內容，如「最高 7% 回饋」「首購 9 折」「滿 200 元免運」"
    )


class DMMetadata(BaseModel):
    """整本 DM 共通的 metadata。

    從 cover / index / promotion 頁的 OCR 內容由 LLM 抽取。後續 RAG query
    path 把此 metadata prepend 到 LLM system context（不重 embed），補足
    chunks 缺失的時間/商家/會員/跨頁活動背景。
    """

    dm_name: str = Field(
        default="",
        description="DM 名稱，如「家樂福 4 月 DM」「家樂福春季號」。找不到填空字串。",
    )
    dm_period: str = Field(
        default="",
        description=(
            "DM 有效期間，YYYY/MM/DD~YYYY/MM/DD 格式（即使 OCR 用 4/8~4/30 縮寫"
            "也展開為完整年月日）。找不到填空字串。"
        ),
    )
    merchant: str = Field(
        default="",
        description="商家名稱，如「家樂福」「全聯」「家樂福 + 中國信託」",
    )
    member_conditions: list[MemberCondition] = Field(
        default_factory=list,
        description=(
            "會員 / 持卡人專屬條件清單。空清單代表 OCR 內容無此類資訊。"
        ),
    )
    global_activities: list[GlobalActivity] = Field(
        default_factory=list,
        description=(
            "全 DM 適用的跨頁活動（不限定特定商品的「天天 / 每週 / 每月」"
            "活動）。例：天天生鮮日、週二加油日、週四豆米漿日。空清單代表"
            "無此類活動。"
        ),
    )
    featured_categories: list[str] = Field(
        default_factory=list,
        description=(
            "本期主打商品類別（高層次摘要，如「低脂牛奶系列」「麵包饅頭」"
            "「冷凍冰品」「環保家用品」）— 從多頁 OCR 摘要不重複的 3-8 個"
            "類別。空清單代表 OCR 內容無明顯主打分類。"
        ),
    )
    special_activities: list[str] = Field(
        default_factory=list,
        description=(
            "特色活動字串清單（短描述），如「買一送一」「第二件 5 折」"
            "「OPENPOINT 10 倍送」「滿 309 折 30」。空清單代表無特色活動。"
        ),
    )


# ── Implementation ──────────────────────────────────────────────


class LLMDMMetadataExtractor(DMMetadataExtractor):
    """Anthropic tool-use-based extractor — schema-validated JSON output."""

    def __init__(
        self,
        api_key: str = "",
        api_key_resolver: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_key_resolver = api_key_resolver
        self._client: anthropic.AsyncAnthropic | None = None
        if api_key:
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        # Token tracking — 對齊 LLMChunkContextService 5 屬性
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0
        self.last_cache_read_tokens: int = 0
        self.last_cache_creation_tokens: int = 0
        self.last_model: str = ""

    async def _ensure_client(
        self, force: bool = False
    ) -> anthropic.AsyncAnthropic:
        if self._client is not None and not force:
            return self._client
        api_key = self._api_key
        if not api_key and self._api_key_resolver:
            api_key = await self._api_key_resolver("anthropic")
        if not api_key or not api_key.strip():
            raise RuntimeError(
                "Anthropic API key not configured for DM metadata extractor"
            )
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    async def extract(
        self,
        *,
        ocr_excerpts: list[str],
        page_types: list[str],
        model: str = "",
    ) -> dict[str, Any]:
        """Extract structured DM metadata from cover/promotion page OCR text.

        Args:
            ocr_excerpts: list of OCR text per source page (each chunked text)
            page_types: parallel list of page_type label per excerpt
                (catalog/promotion/mixed/cover) — informs LLM which is which
            model: optional model override (default: claude-haiku-4-5)

        Returns:
            dict matching DMMetadata Pydantic schema. On extraction failure
            returns ``{}`` (caller should treat as 「不啟用」 not crash).
        """
        # Reset token counters
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self.last_cache_read_tokens = 0
        self.last_cache_creation_tokens = 0

        if not ocr_excerpts:
            return {}

        if len(page_types) != len(ocr_excerpts):
            page_types = ["unknown"] * len(ocr_excerpts)

        resolved_model = model or DEFAULT_MODEL
        self.last_model = resolved_model

        prompt = self._build_prompt(ocr_excerpts, page_types)
        tool_def = self._build_tool_definition()

        log = logger.bind(
            model=resolved_model,
            excerpt_count=len(ocr_excerpts),
            prompt_chars=len(prompt),
        )
        log.info("dm_metadata.extract.start")

        for attempt in (0, 1):
            try:
                client = await self._ensure_client(force=attempt == 1)
                t0 = time.perf_counter()
                response = await client.messages.create(
                    model=resolved_model,
                    max_tokens=MAX_OUTPUT_TOKENS,
                    tools=[tool_def],
                    tool_choice={"type": "tool", "name": TOOL_NAME},
                    messages=[{"role": "user", "content": prompt}],
                )
                elapsed_ms = round((time.perf_counter() - t0) * 1000)

                usage = response.usage
                self.last_input_tokens = usage.input_tokens
                self.last_output_tokens = usage.output_tokens
                self.last_cache_read_tokens = (
                    getattr(usage, "cache_read_input_tokens", 0) or 0
                )
                self.last_cache_creation_tokens = (
                    getattr(usage, "cache_creation_input_tokens", 0) or 0
                )

                # 解析 tool_use block
                tool_use = next(
                    (b for b in response.content if b.type == "tool_use"),
                    None,
                )
                if tool_use is None:
                    log.warning(
                        "dm_metadata.extract.no_tool_use",
                        stop_reason=response.stop_reason,
                    )
                    return {}

                raw_input = tool_use.input
                # Pydantic 二次驗證 — 確保 dict 符合 schema
                metadata = DMMetadata.model_validate(raw_input)
                result = metadata.model_dump()

                log.info(
                    "dm_metadata.extract.done",
                    elapsed_ms=elapsed_ms,
                    input_tokens=self.last_input_tokens,
                    output_tokens=self.last_output_tokens,
                    cache_read_tokens=self.last_cache_read_tokens,
                    cache_creation_tokens=self.last_cache_creation_tokens,
                    fields_extracted=sum(
                        1 for v in result.values() if v
                    ),
                )
                return result

            except anthropic.AuthenticationError:
                if attempt == 0:
                    self._client = None
                    continue
                log.warning("dm_metadata.extract.auth_failed", exc_info=True)
                return {}
            except ValueError as e:
                if "Illegal header value" in str(e) and attempt == 0:
                    self._client = None
                    continue
                log.warning("dm_metadata.extract.value_error", exc_info=True)
                return {}
            except anthropic.APIError:
                log.warning("dm_metadata.extract.api_error", exc_info=True)
                return {}

        return {}

    @staticmethod
    def _build_tool_definition() -> dict[str, Any]:
        """Build Anthropic tool definition from Pydantic schema.

        Anthropic 的 input_schema 接 JSON schema (draft-7 ish)，Pydantic 的
        ``model_json_schema()`` 直接相容。``$defs`` 形式的 nested model
        Anthropic 也認得。
        """
        schema = DMMetadata.model_json_schema()
        return {
            "name": TOOL_NAME,
            "description": (
                "Persist extracted DM-level metadata. Call this exactly once "
                "with all fields you can extract from the OCR excerpts. "
                "Leave fields as empty string / empty list if the OCR content "
                "does not contain that information — do not invent data."
            ),
            "input_schema": schema,
        }

    @staticmethod
    def _build_prompt(
        ocr_excerpts: list[str], page_types: list[str]
    ) -> str:
        """Compose the user message — labelled OCR excerpts."""
        # Truncate to budget
        sections: list[str] = []
        total = 0
        for excerpt, ptype in zip(ocr_excerpts, page_types, strict=True):
            section = f"=== Page Type: {ptype} ===\n{excerpt}\n"
            if total + len(section) > MAX_OCR_CHARS:
                section = section[: max(0, MAX_OCR_CHARS - total)]
                sections.append(section)
                break
            sections.append(section)
            total += len(section)

        ocr_blob = "\n".join(sections)
        return (
            "你是 DM 結構化 metadata 抽取專家。下方是同一本 DM 多頁的 OCR "
            "內容（每頁有 page_type 標註）。請只從 OCR **顯式包含**的資訊"
            "中抽取，**不要編造**。\n\n"
            "重點觀察：\n"
            "- DM 期間：通常印在封面或結尾頁，找出 YYYY/MM/DD~YYYY/MM/DD 區間\n"
            "- 商家：從 logo / 印章 / 客服資訊判斷\n"
            "- 跨頁活動：「天天生鮮日 / 週二加油日 / 週四豆米漿日」這類**全 DM "
            "適用的固定活動**（區別於單頁特價）\n"
            "- 會員條件：unipen 聯名卡 / App 會員 / 新會員等專屬條件\n"
            "- 主打商品類別：從多頁商品看出本期主打的 3-8 個類別摘要\n"
            "- 特色活動：「買一送一 / 第二件 5 折 / OPENPOINT 10 倍送」等\n\n"
            "找不到的欄位填空字串 / 空清單，**不要編造**。\n\n"
            "DM OCR 內容：\n\n"
            + ocr_blob
            + "\n\n請呼叫 save_dm_metadata 工具回傳結構化結果。"
        )
