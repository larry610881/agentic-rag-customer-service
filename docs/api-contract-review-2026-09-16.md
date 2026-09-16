# API 契約審核 — 第二塊：全 API 面（2026-09-16）

> 依 `restful-api-contract-review` 準則（A1–F5）對整個 HTTP API 面跑一次。
> 底稿：由 `create_app().openapi()` 產出的 spec（187 路徑、235 操作、224 schema，其中回應 schema 130 個）。
> 方法：機械 schema lint（型別、日期、可空集合、列舉、JSON 字串、金額、宣告的狀態碼）＋ 程式層 grep
> （錯誤碼、cookie、序列化設定、SSE 語意、冪等）。第一塊（`/agent/chat`，#94／#95）已完成，本文不重複。
> 通過項與不適用項列在文末。**寧可少報**：每個發現都附機械證據，未驗證者標 `[待驗證]`。

## 1. 發現

| 嚴重度 | 位置 | 失效情境 | 業務影響 |
|---|---|---|---|
| **Critical** | 29 個 `format: date-time` 回應欄位（`ApiKeyResponse.created_at`、`ConversationSummaryResponse.*`…）；序列化為 Pydantic 2.13 預設 | 同一欄位兩種形狀：微秒為 0 時 `2026-09-16T10:00:00Z`，否則 `…T10:00:00.123456Z`（實測見 §3）。Swift `.iso8601` 開 `withFractionalSeconds` 後遇整秒那筆解碼失敗，反之亦然 | 原生 app 列表頁間歇性整頁失敗，且極難重現 |
| **High** | 全部 235 操作只宣告 200/201/202/204/422；未宣告任何 4xx/5xx body schema | 客戶端產生器不會產出錯誤 model；`code` 是 #94 加的但 OpenAPI 沒說 | 原生端只能手寫錯誤解析，每次改文案都可能壞 |
| **High** | 207 處 `HTTPException(detail="<句子>")` 分布 30 個 router（bot 17、widget 12、eval_dataset 8、auth 8、pricing 8…） | 只拿到依狀態碼推斷的通用 `code`（`not_found`／`forbidden`／`conflict`），同一狀態碼的不同原因無法區分 | 客戶端無法對「bot 不存在」與「KB 不存在」做不同處理 |
| **High** | 22 個回 201 的 POST 都不接受 `Idempotency-Key`（`/knowledge-bases/{kb}/documents`、`/bots`、`/api-keys`、`/feedback`…） | 行動網路回應遺失後重送 → 重複文件、重複 bot、重複回饋 | 文件上傳重複會重複 embedding 計費 |
| **High** | 9 個回應欄位為「可空陣列」：`BotResponse.guard_stages`、`MessageItem.retrieved_chunks`、`WorkerResponse.enabled_tools`、`TenantResponse.included_categories`… | Swift 非 Optional `[T]` 遇 `null` 拋 `valueNotFound`；Kotlin 預設 `explicitNulls` 需 `List<T>?` | 客戶端必須為每個集合寫可空分支 |
| **High** | SSE：`/agent/chat/stream`、`/widget/{code}/chat/stream`、`/prompt-optimizer/runs/*/stream` 無 `id:`、無 `Last-Event-ID`、事件型別清單不在契約；widget 無非串流替代端點 | 進背景斷線後無法重連去重；瀏覽器原生 `EventSource` 不能帶 `Authorization` 與 body | 原生端要自寫 SSE reader 且無法續傳 |
| **Medium** | 24 個金額欄位為 `number`：`*.estimated_cost`、`GateRunResponse.est_cost/actual_cost`、`ModelConfigSchema.input_price/output_price`、`DryRunRecalculateResponse.cost_*` | 三端浮點四捨五入不一致 | 對帳時差一分錢 |
| **Medium** | 21 個無型別 `object` 回應欄位：`BotResponse.output_schema/tool_configs`、`MessageItem.structured_content`、`GateRunResponse.details`、`OutboxEventResponse.payload`… | Swift 無 `AnyCodable`，每個都要自寫包裝；其中 `structured_content` 已在 #94 對 chat 端點 typed，歷史端點仍是 dict | 型別安全在該點消失 |
| **Medium** | `openapi.json` 未由程式產出提交；production 關閉 `/openapi.json`；無 `oasdiff` | 契約漂移只能靠人眼（第一塊就抓到 4 處） | 每次改動廠商端才發現 |
| **Medium** | CORS 未 `expose_headers`（`main.py:291`）：`Retry-After`、`X-RateLimit-*`、`X-Request-ID`、`Idempotent-Replayed` 瀏覽器讀不到 | widget／WebView 429 只能盲目重試，回報問題拿不到 request_id | 支援成本 |
| **Medium** | 無 `X-Client-Version`、無 426 最低版本門檻 | 出事時無法辨識哪個版本在打 | 無法引導更新 |

已順手修（本次 commit）：
- `errors.py` 對 dict 形式 `detail`（`{"code","message","violations"}`，`bot_config_version_router.py:180/185`）改為 `code` 沿用、`message` 當 `detail`、其餘攤平——#94 引入的回歸，原本會把 dict 轉成字串當 detail。
- widget 串流的 `conversation_id` 事件補 `conversation_created`（#94 只做了 web，違反三通路一致）；helper 移到 `_stream_events.py` 共用。

## 2. 通過／不適用／覆蓋限制

- **通過**：A1（130 個回應 schema 無同 key 多型別）、A4（回應無封閉列舉，皆為純字串）、A5（無 string 承載 JSON 的欄位，chat 的 `answer` 已在 #94 加 typed `output`）、C4（只走 `Authorization`／widget 票，無 cookie）、D2（chat 已有 `conversation_created`；widget 本次補齊）、D5（Pydantic 對必要欄位錯型別回 422）。
- **A2 補充**：DB 49 個 `DateTime` 欄位全部 `timezone=True`、程式 270 處皆用 `datetime.now(timezone.utc)`、無 naive 產生點——所以 `Z` 是穩定的，只有小數位不穩定。
- **不適用**：B1／B2／B3（除 chat 外尚無對外發布的版本）、E2／E3（無官方 SDK 與 fixture）、F1／F2（PR 流程，屬治理）。
- **覆蓋限制**：未對每個端點實際打請求；SSE 未做切割點窮舉測試；LINE webhook 屬入站協定不在本審核範圍。

## 3. 證據

```
# Pydantic 2.13.5，aware datetime
us=0     → {"t":"2026-09-16T10:00:00Z"}
us=1000  → {"t":"2026-09-16T10:00:00.001000Z"}
```
```
宣告的回應狀態碼分布: {'200': 186, '422': 215, '201': 22, '204': 20, '202': 7}
句子型 detail 的 raise：207 處（依檔案：bot 17、widget 12、eval_dataset 8、auth 8、admin_pricing 8、
bot_config_version 7、tenant 6、knowledge_base 6、admin 6 …）
```

## 4. 改造順序（全部加法，前半段不弄壞 web）

| # | 項目 | 做法 | 估時 | 對應 |
|---|---|---|---|---|
| 1 | **日期單一 profile** | `ApiDateTime = Annotated[datetime, PlainSerializer(→ UTC、`Z`、固定三位小數)]`，29 個回應欄位改型別；OpenAPI 加 `pattern`；serializer 測試 us=0／123456 | 0.5 天 | A2、E4 |
| 2 | **錯誤 schema 進 OpenAPI** | 定義 `ErrorResponse{detail, code, request_id}`，`app = FastAPI(responses={401/403/404/409/422/429: ErrorResponse})`；422 用 `ValidationErrorResponse`（多 `errors`） | 0.5 天 | D3、A1 |
| 3 | **錯誤碼分批補齊** | 依 router 逐批把 207 處句子型 detail 改 `ApiError(code=…)`；先做對外面：auth、api_key、bots、knowledge_bases、documents、conversations（約 60 處），其餘留 `infer_code` | 1.5 天 | D3、C2 |
| 4 | **集合永遠 `[]`** | 9 個可空陣列改 `list[T] = Field(default_factory=list)`；web 前端用 `??`／`?.length` 不受影響（已 grep） | 0.5 天 | A3 |
| 5 | **OpenAPI 由程式產出並提交** | `scripts/export_openapi.py` → `docs/api/openapi.json`；unit test 斷言與提交版本一致；CI 加 `oasdiff breaking` | 0.5 天 | E1、B1 |
| 6 | **CORS expose_headers** | `Retry-After`、`X-RateLimit-*`、`X-Request-ID`、`Idempotent-Replayed` | 0.1 天 | D4 |
| 7 | **`Idempotency-Key` 擴到建立型端點** | 重用 `IdempotencyGuard`；先做會計費或會重複資料的：documents 上傳、bots、api-keys、feedback、prompt-optimizer runs | 1 天 | D1 |
| 8 | **SSE 契約** | 事件型別清單進文件；`id:` 用事件序號、支援 `Last-Event-ID` 從快照重播（與 #95 串流冪等合併做）；widget 加非串流端點 | 2 天 | C3 |
| 9 | **金額改字串或明定最小單位** | 24 個 `number` 金額欄位加 `*_str` 或改 `Decimal` 序列化為字串；舊欄位標 deprecated | 1 天 | A7 |
| 10 | **無型別 object 標 opaque** | 21 個欄位加 `x-opaque: true` 與用途說明；`structured_content` 歷史端點改 typed（與 chat 對齊） | 0.5 天 | A6 |
| 11 | **`X-Client-Version` + 426** | 中介層讀標頭、最低版本設定、`426` + `code=client_upgrade_required` | 0.5 天 | B4 |

**建議先做 1–6**（共約 3.5 天）：都是加法、都不需要 migration、做完後原生端的解碼風險就從「間歇性失敗」降到「可預期」。7–11 依廠商接入進度排。

## 5. 不做的事

- 不把 `detail` 改成 RFC 9457 的 `title/type/instance` 全套：`{detail, code, request_id}` 已滿足 D3，多的欄位沒有消費者。
- 不為 LINE webhook 做契約審核：它是入站協定，由 LINE 定義。
- 不強制所有 POST 都接 `Idempotency-Key`：只做會計費或會產生重複資料的。
