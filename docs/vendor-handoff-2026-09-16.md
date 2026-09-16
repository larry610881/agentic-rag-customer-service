# 3D 展廠商交付包（`/api/v1/agent/chat` 整合）— 2026-09-16

> 對象：3D 展測試機供應商（LumiOne → agentic-rag 切換）。線上版本：Cloud Run rev `agentic-rag-00031-2cr` 之後。

## 交付內容

| 項目 | 位置 | 說明 |
|---|---|---|
| 整合規格 | `docs/agent-chat-api-spec.md` | 端點、標頭、body、`conversation_id` 語意、錯誤碼、重送語意 |
| OpenAPI | `docs/api/openapi.json` | 由程式產出並提交（含全部 4xx body schema、`Idempotency-Key` / `Last-Event-ID` 標頭參數），可直接餵 Swift / Kotlin 產生器 |
| SSE 契約 | `docs/api/sse-contract.md` | 事件型別清單、`id:` 序號、終止語意、reader 規則、快照重播 |
| Redis / 冪等 | `docs/redis-keyspace.md` | 重送保護的保留期與降級行為 |

## 產生器建議設定（準則 E2）

- swift5：`enumUnknownDefaultCase=true`；日期解析接受 0–9 位小數（伺服器固定輸出三位 `Z`）。
- Kotlin：`kotlinx.serialization`，`ignoreUnknownKeys=true`、`coerceInputValues=true`。
- 錯誤 model：`ErrorResponse{detail, code, request_id}`；422 用 `ValidationErrorResponse`（多 `errors`）。客戶端依 `code` 分支，不依 `detail` 文案。

## 廠商必答（接入前）

1. **`client_secret` 存放位置**：放在展場測試機本機，還是廠商自己的後端？若在裝置上，請改由廠商後端代換 token（機器票 15 分鐘），裝置不持有 secret。
2. **重送策略**：逾時 10 秒／連線 3 秒；逾時或 5xx 重送時帶同一把 `Idempotency-Key` 與同一個 `conversation_id`。
3. **`X-Client-Version`**：原生 app 每次請求都帶，格式 semver（如 `1.2.0`），供平台依版本聚合與必要時 426 止血。
4. **兩個 bot 的對話 id 分開保存**：同一個 `conversation_id` 拿去打另一個 bot 會靜默開新對話（回應 `conversation_created: true`）。
5. **金額欄位**：`usage.estimated_cost` 為六位小數的 number，另有 `estimated_cost_str`；對帳請用字串。

## 平台端待辦（廠商回覆後）

- 廠商確認 secret 存放方式後，若需裝置持有，改發 per-install 憑證（另案）。
- 廠商版本號格式確認後，設定 `min_client_version`（目前空 = 不檢查）。
