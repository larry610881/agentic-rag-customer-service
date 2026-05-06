"""Claude Vision OCR engine using Anthropic Python SDK.

支援兩種 OCR pipeline：
- 單一 prompt 模式（``ocr_mode="catalog"`` / ``"general"``）：caller 拿
  ``OCR_PROMPTS[mode]`` 字串呼叫 ``ocr_page(img, prompt)``。
- Auto-dispatch 模式（``ocr_mode="auto"``）：caller 改呼叫
  ``ocr_page_auto_dispatch(img)``，內部先用 Haiku 做頁面類型偵測
  （catalog / promotion / mixed / cover），再用對應 prompt 做 OCR。
  解決 5/6 carrefour DM 第 2、8、64 頁等「信用卡聯名卡 / APP 推廣 /
  服務介紹」純優惠頁因為走 _CATALOG_PROMPT 解不出活動條件的問題。
"""

from __future__ import annotations

import asyncio
import base64
import io
import time

import anthropic

from src.domain.shared.exceptions import OcrProcessingError
from src.infrastructure.file_parser.ocr_engines.base import OcrEngine
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_MAX_IMAGE_BYTES = 3_500_000  # ~3.5MB raw → ~4.7MB after base64 (stays under Claude's 5MB limit)

_DEFAULT_PROMPT = (
    "Extract all visible text from this page. "
    "Return only the text content in reading order. No commentary."
)

_CATALOG_PROMPT = """\
你是賣場 DM 結構化提取專家。分析這張頁面，依以下規則輸出：

【頁面分類】先判斷頁面類型：商品頁 / 促銷活動頁 / 資訊頁

■ 若為「商品頁」或「促銷活動頁」，逐一列出每個商品：
===
商品：{完整商品名稱}
品牌：{品牌名，若可辨識}
規格：{容量/重量/尺寸/數量/包裝}
原價：{原價，若有刪除線或標示「原價」}
售價：{現售價，含計量單位如「元/瓶」}
促銷：{買一送一/第二件5折/加價購/會員價/10倍送等，若有}
備註：{產地/型號/能效/坪數等額外資訊，若有}
===

■ 若為「資訊頁」（信用卡優惠、APP推廣、活動辦法等），
以段落方式摘要重點，保留關鍵數字與日期。

規則：
- 若頁面有大標題或活動主題（如「TOP10 熱銷排行榜」「OPEN Day 加購」「最後3天 結帳再95折」「新品上市」），
  在最前面獨立標註：【頁面標題】完整標題文字
  （標題是 user 在 LINE 問問題時最常用的關鍵字，必須抽出）
- 若頁面包含活動日期（如「4/8～4/21」），標註：【活動期間】YYYY/MM/DD～YYYY/MM/DD
- 若頁面包含商家名稱（如「家樂福」「全聯」），標註：【商家】名稱
- 若頁面有適用於整頁所有商品的「頁面級促銷說明」（如「滿309折30」「會員專屬9折」「全店買2件再95折」），
  獨立標註：【頁面級促銷說明】完整說明文字
  （這跟個別商品的「促銷」欄不同，這是適用全頁的條件）
- 每個商品獨立一組 ===，不可合併
- 價格保留「元/瓶」「元/包」「元/台」等計量
- 看不清楚的欄位填「不詳」，不要猜測

範例輸出（商品頁含標題與頁面級促銷）：
【頁面標題】TOP10 熱銷排行榜
【商家】家樂福
【活動期間】2026/04/08～2026/04/21
【頁面分類】商品頁（TOP熱銷排行榜）
【頁面級促銷說明】單筆購買 TOP 商品任 2 件再享 9 折

===
商品：好米花蓮玉里有機米
品牌：好米
售價：499元/包
===
"""

_PROMOTION_PROMPT = """\
你是 DM 純優惠介紹頁的結構化提取專家。這頁無商品列表，只有活動/服務介紹
（信用卡聯名卡、會員活動、折扣券、線上購物導覽、APP 服務、滿額禮等）。

請依以下格式逐行輸出，**不要敘事體**：

【活動主題】完整活動標題（如「中國信託聯名卡」「家樂宅 4 周年慶」「天天享優惠」）
【活動期間】YYYY/MM/DD～YYYY/MM/DD（若標示）
【商家】家樂福 / 中國信託 / 第三方品牌等
【優惠對象】哪類客群、哪類消費（如「新會員首購」「滿 $XXX」「家樂福 unipen 聯名卡持卡人」）
【優惠條件】每行一條「條件 → 回饋/折扣」具體格式
  範例：
  - 綠色商品消費 → 7% 回饋
  - 第二件 5 折
  - OPENPOINT 點數兌換 → 加碼 X 點
  - 滿 $200 免運（線上購物）
【適用範圍】哪些通路（線上/實體/特定門市）、哪些商品（部分/全店/排除項目）
【數量限制】每月限 1 次 / 累積上限 NT$X / 贈品數量有限等
【聯絡方式】客服電話 / 網址 / QR code 描述（如有）
【其他注意事項】條款限制（適用整頁的注意點，如「逾期作廢」「不適用 XX」）

規則：
- 找不到的欄位填「不詳」，不要省略整個欄位
- 「活動主題」和「商家」必抽全（這是 user 在 LINE 問問題時最常用的關鍵字）
- 優惠條件即使有 5 條以上也要全列，每條獨立一行
- 數字、日期、百分比、金額必須完整保留（如「2026/4/1」「7%」「NT$500」）
"""

_MIXED_PROMPT = """\
你是 DM 結構化提取專家。這頁同時包含商品列表 + 活動/促銷條款（例如：
半頁商品 + 半頁信用卡分期條款，或商品專區 + 滿額活動詳情）。請分兩段輸出：

## 商品段

【頁面標題】完整標題文字（如「TOP10 熱銷排行榜」「安心價」）
【商家】家樂福 / 全聯
【活動期間】YYYY/MM/DD～YYYY/MM/DD
【頁面級促銷說明】整頁適用的促銷（如「滿 309 折 30」「會員 9 折」）

===
商品：{完整商品名稱}
品牌：{品牌名}
規格：{容量/重量/尺寸}
原價：{原價}
售價：{現售價含計量單位}
促銷：{買一送一/第二件 5 折等個別商品促銷}
備註：{產地/型號/能效等}
===

（每個商品獨立一組 ===，不可合併）

## 活動段

【活動主題】完整活動標題
【活動期間】
【優惠對象】
【優惠條件】每行一條「條件 → 回饋/折扣」
【適用範圍】
【數量限制】
【其他注意事項】

規則：
- 兩段都必須輸出，不可省略其中一段
- 商品段格式參考「商品頁」既有規範，活動段參考「優惠介紹頁」規範
- 看不清楚的欄位填「不詳」
"""

_COVER_PROMPT = """\
這是 DM 的封面 / 目錄 / 結尾 / 店鋪資訊頁（語意稀薄頁）。請抽：

【DM 名稱】（如「家樂福 4 月 DM」）
【DM 期間】YYYY/MM/DD～YYYY/MM/DD
【商家】家樂福
【主要區段】（若為目錄頁，列出各區段標題）
【聯絡電話】客服 / 直營門市總機
【官網】URL 或文字描述
【APP】APP 名稱 / 下載方式描述
【店鋪資訊】（營業時間、地址、加油站、停車優惠等，若有）
【其他】

規則：
- 簡潔列出，無相關欄位填「不詳」
- 此類頁語意密度低，輸出可比商品頁短
"""

_CLASSIFY_PROMPT = """這是 DM 的某一頁。請分類為下列其中一種，**只回單一英文 token**：

- catalog: 商品列表頁（多個具體商品照 + 價格 + 商品名）
- promotion: 純優惠/服務介紹頁（信用卡 / 會員 / 折扣券 / APP 導覽 / 服務介紹，無具體商品列表，或商品只是裝飾性配圖）
- mixed: 混合頁（明顯同時有商品列表 + 大塊優惠/活動條款）
- cover: 封面 / 目錄 / 結尾 / 店鋪營業時間 / 加油站資訊

只回 catalog / promotion / mixed / cover 其中之一，不要解釋。
"""

# Page-type → OCR prompt mapping，給 auto dispatch 模式用。
_PAGE_TYPE_PROMPTS: dict[str, str] = {
    "catalog": _CATALOG_PROMPT,
    "promotion": _PROMOTION_PROMPT,
    "mixed": _MIXED_PROMPT,
    "cover": _COVER_PROMPT,
}

_VALID_PAGE_TYPES: frozenset[str] = frozenset(_PAGE_TYPE_PROMPTS.keys())

OCR_PROMPTS: dict[str, str] = {
    "general": _DEFAULT_PROMPT,
    "catalog": _CATALOG_PROMPT,
    # "auto" 模式不對應靜態 prompt — caller 必須改呼叫
    # ClaudeVisionOcrEngine.ocr_page_auto_dispatch()，由 engine 內部偵測
    # 頁面類型再 dispatch 至 _PAGE_TYPE_PROMPTS。
}


def _compress_image(image_bytes: bytes) -> tuple[bytes, str]:
    """Compress image to fit within Claude API size limit.

    Returns (image_bytes, media_type).
    """
    if len(image_bytes) <= _MAX_IMAGE_BYTES:
        return image_bytes, "image/png"

    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    for quality in (85, 70, 50, 30):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= _MAX_IMAGE_BYTES:
            return buf.getvalue(), "image/jpeg"

    # Still too large — scale down
    scale = 0.7
    while scale > 0.2:
        new_size = (int(img.width * scale), int(img.height * scale))
        resized = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=60)
        if buf.tell() <= _MAX_IMAGE_BYTES:
            return buf.getvalue(), "image/jpeg"
        scale -= 0.1

    buf = io.BytesIO()
    img.resize((int(img.width * 0.2), int(img.height * 0.2)), Image.LANCZOS).save(
        buf, format="JPEG", quality=40
    )
    return buf.getvalue(), "image/jpeg"


class ClaudeVisionOcrEngine(OcrEngine):
    """OCR engine that uses Claude Vision API for text extraction."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-haiku-4-5-20251001",
        max_concurrent: int = 5,
        api_key_resolver=None,
    ) -> None:
        self._api_key = api_key
        self._api_key_resolver = api_key_resolver  # async (provider_name) -> str
        self._client: anthropic.AsyncAnthropic | None = None
        if api_key:
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrent)
        # Accumulated usage from last parse batch (reset per batch)
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0

    async def _ensure_client(self, force: bool = False) -> anthropic.AsyncAnthropic:
        # force=True 強制重新解析 key + 重建 client，用於 auth error retry
        if self._client is not None and not force:
            return self._client
        api_key = self._api_key
        if not api_key and self._api_key_resolver:
            api_key = await self._api_key_resolver("anthropic")
        if not api_key or not api_key.strip():
            # 防禦性：空字串 / 純空白都不能建 client
            # 之前空字串會被當成 truthy（httpx 拒 header）導致整個 worker 後續 OCR 全爆
            raise RuntimeError(
                "Anthropic API key not configured for OCR (empty or whitespace)"
            )
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    async def ocr_page(self, image_bytes: bytes, prompt: str | None = None) -> str:
        prompt = prompt or _DEFAULT_PROMPT
        image_bytes, media_type = _compress_image(image_bytes)
        b64 = base64.standard_b64encode(image_bytes).decode()
        img_kb = len(image_bytes) / 1024
        # 一次 retry：第一次拿到 auth error 時假設 client 帶壞 key，
        # invalidate 後重新解析 key 再試。常見於 worker 啟動時 DB
        # 慢一拍導致首頁 OCR 拿到空 key 緩存的情境。
        for attempt in (0, 1):
            try:
                client = await self._ensure_client(force=attempt == 1)
                async with self._semaphore:
                    t0 = time.perf_counter()
                    message = await client.messages.create(
                        model=self._model,
                        max_tokens=8192,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": b64,
                                        },
                                    },
                                    {"type": "text", "text": prompt},
                                ],
                            }
                        ],
                    )
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                usage = message.usage
                self.last_input_tokens += usage.input_tokens
                self.last_output_tokens += usage.output_tokens
                logger.info(
                    "ocr.page.done",
                    model=self._model,
                    media_type=media_type,
                    image_kb=round(img_kb),
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    elapsed_ms=elapsed_ms,
                    attempt=attempt,
                )
                return message.content[0].text
            except anthropic.AuthenticationError as e:
                if attempt == 0:
                    logger.warning(
                        "ocr.auth_error.retry",
                        error=str(e),
                        action="invalidate_client_and_resolve_again",
                    )
                    self._client = None  # 強制下次 _ensure_client 重新解析
                    continue
                raise OcrProcessingError(f"Claude auth error: {e}") from e
            except ValueError as e:
                # httpx 對空 Bearer header 會丟 ValueError("Illegal header value")
                if "Illegal header value" in str(e) and attempt == 0:
                    logger.warning(
                        "ocr.illegal_header.retry",
                        error=str(e),
                        action="invalidate_client_and_resolve_again",
                    )
                    self._client = None
                    continue
                raise OcrProcessingError(f"Claude header error: {e}") from e
            except anthropic.APIError as e:
                raise OcrProcessingError(f"Claude API error: {e}") from e
            except (KeyError, IndexError) as e:
                raise OcrProcessingError(str(e)) from e
        # Unreachable — both attempts must either return or raise
        raise OcrProcessingError("OCR exhausted retries")

    async def classify_page_type(self, image_bytes: bytes) -> str:
        """Detect DM page type for auto-dispatch routing.

        Returns one of: ``catalog`` / ``promotion`` / ``mixed`` / ``cover``.
        Falls back to ``catalog`` on classification failure (既有預設行為，
        對 84% 商品列表頁不會改變結果)。
        """
        image_bytes_c, media_type = _compress_image(image_bytes)
        b64 = base64.standard_b64encode(image_bytes_c).decode()

        for attempt in (0, 1):
            try:
                client = await self._ensure_client(force=attempt == 1)
                async with self._semaphore:
                    message = await client.messages.create(
                        model=self._model,
                        max_tokens=20,  # 單 token 就夠
                        messages=[{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": b64,
                                    },
                                },
                                {"type": "text", "text": _CLASSIFY_PROMPT},
                            ],
                        }],
                    )
                usage = message.usage
                self.last_input_tokens += usage.input_tokens
                self.last_output_tokens += usage.output_tokens
                raw = message.content[0].text.strip().lower()
                # 只取第一個 token；防 LLM 多嘴
                token = raw.split()[0] if raw else ""
                # strip 標點
                token = token.rstrip(".,:;！。，；").strip()
                if token in _VALID_PAGE_TYPES:
                    logger.info(
                        "ocr.classify.done",
                        page_type=token,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                    )
                    return token
                logger.warning(
                    "ocr.classify.invalid_response",
                    raw=raw[:100],
                    fallback="catalog",
                )
                return "catalog"
            except anthropic.AuthenticationError as e:
                if attempt == 0:
                    self._client = None
                    continue
                raise OcrProcessingError(f"Claude auth error: {e}") from e
            except ValueError as e:
                if "Illegal header value" in str(e) and attempt == 0:
                    self._client = None
                    continue
                raise OcrProcessingError(f"Claude header error: {e}") from e
            except anthropic.APIError as e:
                # Classification 失敗不應卡住 OCR — fallback catalog 跟舊行為一致
                logger.warning(
                    "ocr.classify.api_error",
                    error=str(e)[:200],
                    fallback="catalog",
                )
                return "catalog"
        raise OcrProcessingError("classify_page_type exhausted retries")

    async def ocr_page_auto_dispatch(
        self, image_bytes: bytes
    ) -> tuple[str, str]:
        """Classify-then-OCR pipeline for ``ocr_mode="auto"``.

        Returns ``(page_type, ocr_text)`` so caller can record the detected
        type into chunk metadata for future-proofing。
        """
        page_type = await self.classify_page_type(image_bytes)
        prompt = _PAGE_TYPE_PROMPTS.get(page_type, _CATALOG_PROMPT)
        text = await self.ocr_page(image_bytes, prompt=prompt)
        # 在 OCR 輸出開頭注入【偵測類型】tag，便於 chunk 後續 inspection 與
        # baseline diff（不影響 catalog 既有 marker 體系，因 prompt 各自會
        # 產生自己的標題）。
        return page_type, f"【偵測類型】{page_type}\n{text}"
