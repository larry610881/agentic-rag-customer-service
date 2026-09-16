# `/api/v1/agent/chat` 對外整合規格

**對象**：3D 展測試機供應商切換（LumiOne → agentic-rag）
**查證日期**：2026-09-10，對照線上 rev `00026-k46` 的實際程式碼，非規劃稿。
**2026-09-11 更新**：依 Issue #94 契約加固（分支 `feature/api/chat-contract-hardening`，**尚未部署**）
補上 `conversation_created`、`structured_content.output`、錯誤 `code` / `request_id`；標「#94」的段落
在部署前線上仍是舊行為。

---

## 0. 三個先講的重點

1. **JSON bot 的答案在 `answer` 裡，是一個 JSON 字串，不是已解析的物件。**
   #94 起同一物件也放在 `structured_content.output`（已解析），請優先讀它；`answer` 維持字串相容。
2. **客戶端自訂的 `conversation_id` 不會生效。** 查不到、不屬於這把金鑰的租戶、或**不是同一個 bot**
   建立的對話，都會另開新對話並回傳平台自己的 id。#94 起回應帶 `conversation_created` 旗標可察覺。
   第一輪不要帶，從回應取 id 存起來，後續輪帶平台 id，**且每個 bot 各存一份**。
3. **請求端無法調節模型參數。** 三個會影響生成／檢索的欄位（`config_override`、
   `test_mode`、`history_override`）對 API 客戶端一律 403，必須帶 eval 標記且具 admin 角色才可用。
   模型溫度、檢索門檻、rerank、工具啟用全部留在後台 bot 設定。

---

## 1. 端點

```
POST https://agentic-rag-entoontwxa-de.a.run.app/api/v1/agent/chat
```

需要的 scope：`chat:send`。

## 2. 標頭

| 標頭 | 必填 | 限制 | 說明 |
|---|---|---|---|
| `Authorization` | 是 | `Bearer <access_token>` | access token 由 `client_id` + `client_secret` 交換取得，效期 15 分鐘 |
| `Content-Type` | 是 | `application/json` | |
| `X-End-User-Id` | 否 | 字串，超過 128 字元會被截斷 | 決定異常控管主體。**不帶的話整把金鑰算同一個主體**，一個使用者狂打會拖累所有人。內容無格式驗證，建議送不可反查的穩定摘要（HMAC）。此值進告警／報表前會被遮成「前 4 碼…後 2 碼」 |
| `X-Usage-Category` | 否 | — | 僅 eval／影子執行用，一般整合不需要也不應帶 |
| `X-Client-Version` | 否，**原生 app 必帶** | semver，如 `1.2.0` | #98。進 request log 供依版本聚合；平台設定最低版本後，低於門檻回 426 `client_upgrade_required`（body 帶 `min_client_version`）。不帶則不檢查 |
| `Idempotency-Key` | 否，**建議帶** | 1–128 可見 ASCII，建議 UUID v4 | #95。每則訊息一把新 key；**逾時或 5xx 重送時帶同一把**。24 小時內同 key 同 body 回同一份回應（含同一個 `conversation_id`），不會再開對話、不再扣用量。見 §6.1 |

## 3. 請求 body

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|---|---|---|---|---|
| `message` | string | **是** | — | 使用者問句 |
| `bot_id` | string \| null | 實務上必填 | `null` | 指定 bot。會對照金鑰的 `allowed_bot_ids` 檢查，不在清單內回 403 |
| `conversation_id` | string \| null | 否 | `null` | 見第 4 節。儲存欄位為 `String(36)`，**上限 36 字元**，不要求 UUID，冒號可接受 |
| `knowledge_base_id` | string \| null | 否，**請勿帶** | `null` | 帶了只會覆寫「主要知識庫」這個欄位；檢索範圍一律取自 bot 綁定的知識庫，帶不帶都無法擴大範圍 |
| `identity_source` | string \| null | 否 | `"web"` | 只影響 trace 的來源標記，不影響行為 |
| `config_override` | object \| null | 否，**會 403** | `null` | 覆寫 bot 設定。未帶合法 eval 標記 + admin 角色 → 403 |
| `test_mode` | boolean | 否，**會 403** | `false` | 影子執行，同上 |
| `history_override` | array \| null | 否，**會 403** | `null` | 注入對話歷史，同上 |

> 後三個欄位是唯一會影響生成或檢索行為的欄位，且對 API 客戶端全部封閉。這就是「模型參數留在後台」在程式層的保證。

## 4. `conversation_id` 的實際行為（重要）

程式邏輯：

```
帶了 conversation_id
  └─ 查得到該對話，且 tenant 與 bot 都吻合 → 沿用，接續歷史（conversation_created: false）
  └─ 查不到，或 tenant / bot 不符           → 不沿用，開一筆全新對話（conversation_created: true）
沒帶 → 開新對話（conversation_created: true）
```

**bot 不符也算歸屬不符**：同一個 `conversation_id` 拿去打另一個 bot（例如看板 → 門市助手），
會靜默開新對話。兩個 bot 的對話 id 必須分開保存。

**客戶端無法用自己的字串建立對話。** 這是刻意設計，防止 A 租戶帶 B 的 `conversation_id`
讀到對方歷史。送 `fab:{uid}` 這類自訂代號會導致每一輪都是新對話、歷史永遠累積不起來，
而且**不會報錯**。

正確接法：

```
第 1 輪   不帶 conversation_id
回應      ChatResponse.conversation_id ← 平台產生的 id（必填欄位，每次都回）
客戶端    存「自己的代號 → 平台 id」對應
第 n 輪   帶平台 id
```

同一段對話若可能先後跑過兩家供應商，客戶端的對應欄位必須帶供應商前綴，否則會把另一家的
id 送過來，命中上面的「歸屬不符 → 另開新對話」。

## 5. 成功回應

```jsonc
{
  "answer": "…",                 // string，必填。JSON bot 時這是 JSON 字串
  "conversation_id": "…",        // string，必填。請存下來
  "conversation_created": true,  // boolean，必填（#94）。true = 本輪新開對話（含帶入的 id 被替換）
  "tool_calls": [                // array，必填（可為空）
    { "tool_name": "…", "label": "…", "reasoning": "…" }
  ],
  "sources": [                   // array，必填（可為空）
    { "document_name": "…", "content_snippet": "…", "score": 0.83 }
  ],
  "structured_content": null,    // object | null（#94 起為 typed 物件，見下）
                                 //   { "contact": object | null,
                                 //     "sources": array（空時 []，不為 null）,
                                 //     "output": object | null（JSON bot 已解析答案）}
  "usage": { … } ,               // object | null，token 用量
  "trace_id": null,              // 僅 test_mode 才有值
  "trace_nodes": null,           // 同上
  "guard_blocked": null,         // 非 studio 來源一律 null
  "guard_rule_matched": null     // 同上
}
```

### 5.1 純文字 bot（fab-3.7）

答案就在 `answer`，純文字。`structured_content` 通常為 `null`（除非該輪有 contact 或 sources）。

### 5.2 JSON bot（card-3.7）

`answer` 是**一個 JSON 字串**，請求端自行 `JSON.parse`。內容符合後台釘死的 schema：

```json
{
  "status": "km | out_of_scope",
  "category": "product-exhibit | marketing | store-ops | unclassified",
  "answer": "繁體中文純文字，不含 Markdown 符號"
}
```

`additionalProperties: false`，三欄全部 required，Gemini 走原生 schema 模式，格式由 API 端保證。

> #94 起同一個已解析物件放在 `structured_content.output`，請求端不必再對 `answer` 做
> `JSON.parse`；`answer` 仍為 JSON 字串以相容舊接法。防護攔截與未命中知識庫時，
> `output` 同樣是符合 schema 的物件。

### 5.3 未命中知識庫

JSON bot 且後台未自訂未命中話術時，`answer` 為：

```json
{"status":"out_of_scope","category":"unclassified","answer":""}
```

（同樣是字串形式）。純文字 bot 則回平台預設話術文字。

## 6. 錯誤回應

#94 起所有 4xx / 5xx 的 body 固定為：

```jsonc
{
  "detail": "…",        // string，給人看，文案可能變動，不要拿來分支
  "code": "…",          // string，穩定的機器可讀碼，請依它分支
  "request_id": "…",    // string，與回應標頭 X-Request-ID 同值，回報問題時附上
  // 依狀態碼可能多出：retry_after（int）、errors（array）、message（string）
}
```

| 狀態碼 | `code` | 情境 | 額外欄位 |
|---|---|---|---|
| 401 | `token_missing` | 未帶 `Authorization` | |
| 401 | `token_expired` | access token 過期 → 重新用 secret 換票 | |
| 401 | `token_invalid` | token 格式錯、簽章錯 | |
| 401 | `token_revoked` | 金鑰已撤銷／過期，換票也會失敗 → 停止重試並聯絡平台 | |
| 402 | `quota_exhausted` | 租戶配額用完 | `message` |
| 403 | `insufficient_scope` | scope 不足；`bot_id` 不在金鑰的 `allowed_bot_ids`（中性，不區分） | |
| 403 | `eval_marker_required` | 使用了 `config_override` / `test_mode` / `history_override` | |
| 422 | `validation_error` | body 欄位型別不符；`detail` 為摘要字串 | `errors`（FastAPI 逐欄位細節陣列） |
| 429 | `rate_limited` | 每分鐘請求數超限 | `retry_after`；標頭 `Retry-After`、`X-RateLimit-*` |
| 429 | `temporarily_unavailable` | 異常控管擋下。**中性回應，不揭露偵測原因** | `retry_after`；標頭 `Retry-After` |
| 400 | `invalid_idempotency_key` | `Idempotency-Key` 格式不合 | |
| 409 | `idempotency_in_progress` | 同一把 key 的第一次請求仍在處理中（並行重送） | 標頭 `Retry-After: 1` |
| 422 | `idempotency_key_reused` | 同一把 key 送了不同的 body | |
| 500 | `internal_error` | 未預期錯誤，請附 `request_id` 回報 | |
| 504 | `request_timeout` | 伺服器端 30 秒逾時（LLM 或檢索過慢） | |

token 換票端點 `POST /api/v1/auth/token` 另有 400 `unsupported_grant_type`、401 `invalid_client`、
403 `invalid_scope`，形狀同上。

伺服器端請求逾時 30 秒（超過回 504）。依實測建議客戶端逾時 10 秒、連線 3 秒，
逾時或 5xx 時重送**必須帶原本的 `conversation_id` 與同一把 `Idempotency-Key`**。

### 6.1 重送語意（`Idempotency-Key`，#95）

- 帶 key 的請求，回應多一個標頭 `Idempotent-Replayed: false`（第一次）／`true`（重播）。
- 第一次成功後快照保留 **24 小時**；期間同 key 同 body 重送直接回快照，伺服器不打 LLM、不開對話、不扣用量。
- 第一次若失敗（4xx / 5xx / 逾時），key 會被釋放，重送會真的重跑。
- 24 小時後同 key 視為新請求。
- 平台 Redis 暫時不可用時退化為無保護（照常處理），屬已知殘餘風險。
- 不帶 key 的請求行為與過去完全相同。

## 7. 範例

### 7.1 純文字 bot，第一輪

```bash
curl -X POST "$BASE/api/v1/agent/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-End-User-Id: 9f2c1a…（HMAC 摘要）" \
  -d '{"message":"甜點櫃有哪些新品？","bot_id":"d1d9d00b-edd9-4e87-879d-d3eeaedd1b33"}'
```

```jsonc
{
  "answer": "本季甜點櫃新增…",
  "conversation_id": "3f9b2c48-…",   // ← 存下來，下一輪帶它
  "conversation_created": true,
  "tool_calls": [],
  "sources": [{ "document_name": "秋季展KM", "content_snippet": "…", "score": 0.78 }],
  "structured_content": null,
  "usage": { "…": "…" }
}
```

### 7.2 JSON bot，第二輪（帶回平台 id）

```bash
curl -X POST "$BASE/api/v1/agent/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-End-User-Id: 9f2c1a…" \
  -d '{"message":"那價格呢？","bot_id":"0fd70ca7-4323-4ae2-a76f-473a8330cf5b","conversation_id":"3f9b2c48-…"}'
```

```jsonc
{
  "answer": "{\"status\":\"km\",\"category\":\"product-exhibit\",\"answer\":\"特價 199 元…\"}",
  "conversation_id": "3f9b2c48-…",
  "conversation_created": false,     // 沿用了帶入的 id
  "tool_calls": [],
  "sources": [ … ],
  "structured_content": {
    "contact": null,
    "sources": [ … ],
    "output": { "status": "km", "category": "product-exhibit", "answer": "特價 199 元…" }
  }
}
```

`answer` 是**字串**；同一個物件已解析放在 `structured_content.output`，請讀後者。

## 8. 本次切換使用的 bot

| 情境 | bot | `bot_id` | 輸出 |
|---|---|---|---|
| 看板 | card-3.7 | `0fd70ca7-4323-4ae2-a76f-473a8330cf5b` | JSON |
| 門市助手 | fab-3.7 | `d1d9d00b-edd9-4e87-879d-d3eeaedd1b33` | 純文字 |

兩隻同為 `gemini-3.7-flash`、同一個知識庫「秋季展KM」、kb 模式、直接檢索、未命中不升級推理。

實測延遲（09-09，各 36 次）：card p50 1,293ms / p95 1,934ms；fab p50 1,103ms / p95 2,461ms。

## 9. 串流端點

`POST /api/v1/agent/chat/stream` 存在，走 SSE，請求 body 與本規格相同。本次整合用不到。
事件層契約（型別清單、`id:` 序號、終止語意、reader 規則）見 repo `docs/api/sse-contract.md`。

## 10. OpenAPI

完整 OpenAPI 由程式產出並提交在 repo `docs/api/openapi.json`（含全部錯誤 body schema 與 `Idempotency-Key` 標頭參數），
可直接餵給 Swift / Kotlin 產生器；production 站台不公開 `/openapi.json`。
