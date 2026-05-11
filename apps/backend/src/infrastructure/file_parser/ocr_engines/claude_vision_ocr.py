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

# 切片補充規則 — caller 啟用切片 OCR 時 prepend 到 prompt 開頭。
# 解決 2x3 切片副作用：商品 card 跨 tile 邊界 → LLM 看到「半個商品」
# 強行填欄位 → 大量 [模糊:???] / 不詳 false positive。
# 解法：明示 LLM「這是切片」、「只輸出完整可見的商品，半個的直接省略」。
_SLICE_AWARE_PREFIX = """\
# 切片補充規則（最高優先級，先於下方所有規則）

**此圖為較大頁面的局部切片**，部分商品 / 活動 block 可能被切到邊緣
（看不到完整商品名 / 看不到價格 / 圖片半張在切片外）。

切片邊緣處理：
- **只輸出能完整看到的商品 / 活動 block**
- 被切到只看到一半的商品 **直接省略**，不要產生不完整 block
- **不要**對切到邊緣的內容填 `[模糊:???]` 或「不詳」 — 直接略過
- 相鄰切片會補上被切到的商品，不用擔心遺漏

下方規則照常套用：

"""

# 共用 OCR 紀律段 — 所有結構化 prompt 開頭都注入這段，防止 LLM 進入
# 「填欄位 → 採樣常見字組 → hallucinate」的失敗模式。
# 對 rare brand char（如「薈」/「樟腦」這類訓練分布稀有的字）特別重要。
_OCR_DISCIPLINE = """\
# OCR 紀律（最高優先級，違反此段即視為任務失敗）

1. **逐字準確**：商品名、規格、品牌字必須照圖中真實字形輸出。

2. **罕用字保護**：罕用字（如「薈」「樟腦」「萃」「茅」「藺」這類）
   若**字形看得清楚**，**直接抄該字**，不要替換為訓練分布中更常見的
   相似字（如把「薈→香/著/奢」、「樟腦→橙醬/橙醛/橙甜」、「萃→葦」、
   「茅→苗」這類常見錯誤）。**寧可看起來奇怪也照字形抄**，看起來奇怪
   不是標 [模糊:???] 的理由。

3. **`[模糊:???]` 的使用時機（嚴格限定）**：
   - ✅ 允許：文字被其他元素**實際遮擋**（重疊貼紙、撕破、嚴重印刷瑕疵）
   - ✅ 允許：解析度真的看不出筆畫（模糊到無法辨認）
   - ❌ **禁止**：「我覺得這字形有點怪」「我不確定是否罕用」→ **直接抄字形**
   - ❌ **禁止**：清晰可見的中英文（如 CLOROX、Bleach 等品牌字）→ **直接抄**
   - 原則：**90% 以上的欄位都應該有真實內容**，[模糊:???] 是例外不是預設

4. **「不詳」的使用時機**：該欄位資訊**不存在**於圖中（如商品沒標品牌、
   沒列出產地、沒寫原價），不用於「我看不清楚」。

5. **字形優先於語意**：字形與你預期語意不符時（例如「樟腦油」覺得奇怪），
   依然按字形輸出，不可改成「合理」的常見字組。

"""

_CATALOG_PROMPT = _OCR_DISCIPLINE + """\
你是賣場 DM 結構化提取專家。分析這張頁面，依以下規則輸出：

# Page-Level Metadata（**必抽 4 項**，找不到填「不詳」不可省略）

依**固定順序**輸出在最前面（每行一個 marker）：
【頁面標題】頁面大標題或活動主題（如「TOP10 熱銷排行榜」「OPEN Day 加購」「最後3天 結帳再95折」「新品上市」「安心價」）— 找不到填「不詳」
【商家】家樂福 / 全聯 / 中國信託 / 全家等（從頁首/頁尾 logo、印章、聯絡資訊判斷）— 找不到填「不詳」
【活動期間】YYYY/MM/DD～YYYY/MM/DD（即使縮寫如「4/8～4/21」也展開為完整年月日；找不到填「不詳」）
【頁面級促銷說明】適用整頁所有商品的條件（如「滿 309 折 30」「會員專屬 9 折」「全店買 2 件再 95 折」「OPENPOINT 10 倍送」）— 找不到填「不詳」

【頁面分類】商品頁 / 促銷活動頁 / 資訊頁

# 商品 blocks（每個商品 1 組 ===）

逐一列出每個商品：

===
商品：{完整商品名稱}
品牌：{品牌名，若可辨識}
規格：{容量/重量/尺寸/數量/包裝}
原價：{原價，若有刪除線或標示「原價」}
售價：{現售價，含計量單位如「元/瓶」}
促銷：{買一送一/第二件5折/加價購/會員價/10倍送等}
備註：{產地/型號/能效/坪數等額外資訊}
===

規則：
- Page-level markers 必抽 4 項（頁面標題/商家/活動期間/頁面級促銷說明）— 找不到填「不詳」，不可省略整個 marker
- 商品 block 之間獨立一組 ===，不可合併
- 價格保留「元/瓶」「元/包」「元/台」等計量
- 個別商品欄位看不清楚填「不詳」

範例輸出：
【頁面標題】TOP10 熱銷排行榜
【商家】家樂福
【活動期間】2026/04/08～2026/04/21
【頁面級促銷說明】單筆購買 TOP 商品任 2 件再享 9 折
【頁面分類】商品頁（TOP熱銷排行榜）

===
商品：好米花蓮玉里有機米
品牌：好米
售價：499元/包
===
"""

_PROMOTION_PROMPT = _OCR_DISCIPLINE + """\
你是 DM 純優惠介紹頁的結構化提取專家。這頁無商品列表，只有活動/服務介紹
（信用卡聯名卡、會員活動、折扣券、線上購物導覽、APP 服務、滿額禮等）。

# Page-Level Metadata（**必抽 3 項**，找不到填「不詳」不可省略）

依**固定順序**輸出在最前面：
【商家】家樂福 / 中國信託 / 全家等（從頁首/頁尾 logo、印章、聯絡資訊判斷）— 找不到填「不詳」
【活動期間】YYYY/MM/DD～YYYY/MM/DD（即使縮寫展開為完整年月日；無期間限制填「不詳」）
【頁面級促銷說明】整頁適用的綜合性條件摘要（一行內，如「unipen 聯名卡綠色消費最高 7% 回饋 + 新會員首購 9 折」）— 找不到填「不詳」

# 活動 blocks（每個獨立活動 1 組 ===）

逐一列出每個獨立活動條目（信用卡分期、會員首購、APP 推廣、滿額禮 等
視為獨立活動）：

===
活動：{活動標題，如「中國信託 unipen 聯名卡」「家樂宅 4 周年慶」「天天享優惠」}
優惠對象：{客群/消費條件，如「新會員首購」「滿 $XXX」「unipen 聯名卡持卡人」「全會員」}
優惠條件：{條件→回饋/折扣，如「綠色商品消費 → 7% 回饋」「第二件 5 折」「滿 $200 免運」}
適用範圍：{通路/商品範圍，如「線上購物」「全店」「特定門市」}
數量限制：{每月限 N 次 / 累積上限 / 贈品數量有限等}
聯絡方式：{客服電話 / 網址 / QR code 描述，若有}
備註：{條款限制 / 排除項目 / 期限備註}
===

規則：
- Page-level markers 必抽 3 項（商家/活動期間/頁面級促銷說明）— 找不到填「不詳」
- 每個獨立活動獨立一組 ===，不可合併（信用卡分期 + 會員首購 → 兩個 block）
- 優惠條件多條時用半形「、」或全形「；」串成一行（保持 1 chunk = 1 活動）
- 數字、日期、百分比、金額必須完整保留（如「2026/04/01」「7%」「NT$500」）

範例輸出：
【商家】家樂福
【活動期間】2026/04/01～2026/04/30
【頁面級促銷說明】中國信託 unipen 聯名卡持卡人最高 7% 回饋 + 新會員首購折扣

===
活動：中國信託 unipen 聯名卡
優惠對象：unipen 聯名卡持卡人
優惠條件：綠色商品消費 → 7% 回饋；OPENPOINT 點數兌換 → 加碼 10 點；單筆滿 1200 元加碼 NT$50
適用範圍：全店、家樂福加油站
數量限制：每月累積上限 NT$500
聯絡方式：客服 0800-001-365
備註：不適用菸酒、悠遊卡儲值
===

===
活動：家樂宅 4 周年慶
優惠對象：新會員首購
優惠條件：首購滿 $200 享 50% off
適用範圍：線上購物
數量限制：每帳號限用一次
聯絡方式：不詳
備註：限活動期間內首次下單
===
"""

_MIXED_PROMPT = _OCR_DISCIPLINE + """\
你是 DM 結構化提取專家。這頁同時包含商品列表 + 活動/促銷條款（例如：
半頁商品 + 半頁信用卡分期條款，或商品專區 + 滿額活動詳情）。

# Page-Level Metadata（**必抽 4 項**，找不到填「不詳」不可省略）

依**固定順序**輸出在最前面：
【頁面標題】（如「安心價」「最後 3 天」）— 找不到填「不詳」
【商家】（家樂福 / 全聯 / 中國信託等）— 找不到填「不詳」
【活動期間】YYYY/MM/DD～YYYY/MM/DD — 找不到填「不詳」
【頁面級促銷說明】整頁適用的促銷條件（一行內）— 找不到填「不詳」

# 兩段內容（**兩段都必須輸出**，不可省略其中一段）

## 商品段

逐一列出每個商品（每商品 1 組 ===）：

===
商品：{完整商品名稱}
品牌：{品牌名}
規格：{容量/重量/尺寸}
原價：{原價}
售價：{現售價含計量單位}
促銷：{買一送一/第二件 5 折等個別商品促銷}
備註：{產地/型號/能效等}
===

## 活動段

逐一列出每個獨立活動（每活動 1 組 ===）：

===
活動：{活動標題}
優惠對象：{客群/消費條件}
優惠條件：{條件 → 回饋/折扣}（多條用全形分號串成一行）
適用範圍：{通路/商品範圍}
數量限制：{每月限 N 次 / 累積上限}
聯絡方式：{客服 / 網址，若有}
備註：{條款限制}
===

規則：
- Page-level markers 必抽 4 項，找不到填「不詳」
- 兩段內容都必須輸出，即使其中一段內容很少（最少 1 個 ===）
- 商品 block 用「商品：」開頭，活動 block 用「活動：」開頭，splitter 依此區分
"""

_COVER_PROMPT = _OCR_DISCIPLINE + """\
這是 DM 的封面 / 目錄 / 結尾 / 店鋪資訊頁（語意稀薄頁，但常含整本 DM
共通的核心 metadata，是 KB-level metadata extraction 的關鍵 input）。

# Page-Level Metadata（**必抽 4 項**，找不到填「不詳」不可省略）

依**固定順序**輸出在最前面：
【DM 名稱】（如「家樂福 4 月 DM」「家樂福春季號」）— 找不到填「不詳」
【DM 期間】YYYY/MM/DD～YYYY/MM/DD（即使縮寫展開為完整年月日）— 找不到填「不詳」
【商家】（家樂福 / 全聯 / 中國信託等）— 找不到填「不詳」
【頁面級促銷說明】此頁適用全 DM 的整體政策（如「天天享優惠 5%」「unipen 聯名卡專屬」）— 找不到填「不詳」

# 其他資訊 blocks（每個區塊 1 組 ===）

逐一列出可辨識的資訊區塊（目錄區段 / 客服資訊 / 店鋪資訊 / 加油站等）：

===
活動：{資訊區塊標題，如「客服資訊」「目錄」「店鋪資訊」}
優惠條件：{該區塊的具體內容，多條用全形分號串成一行}
適用範圍：{適用對象，若有}
聯絡方式：{電話/網址/QR code 描述}
備註：{其他補充}
===

規則：
- Page-level markers 必抽 4 項，找不到填「不詳」
- 此類頁語意密度低，blocks 數量可少（最少 1 個 ===）
- 含「每日活動」（如「天天生鮮日 / 週二加油日」）時，**每個獨立活動 1 個 block**
  （這是後續 KB-level metadata extraction 的關鍵）
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
