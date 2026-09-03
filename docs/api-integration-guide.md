# API 模式串接說明（外部系統 / AI Agent 串接）

> 適用對象：要以程式（而非後台、widget、LINE）呼叫本平台聊天 API 的外部系統。
> 對應 Issue #67 P2；憑證模型見「四種主體各一種憑證」。

## 1. 憑證模型總覽

| 主體 | 憑證 | 取得方式 | 票種 / 有效期 |
|------|------|----------|---------------|
| 人（後台 / Studio） | email + 密碼 | `POST /api/v1/auth/login` | `user_access` 15 分鐘 + `refresh` 7 天（每次換票旋轉、重用即整組撤銷） |
| 機器（本文） | `client_id` + `client_secret` | 租戶管理員在後台「API 金鑰」建立 | `api_access` 15 分鐘，**不發 refresh**，到期用 secret 再換 |
| Widget（瀏覽器） | 無祕密；Origin 白名單 | `GET /api/v1/widget/{code}/config` | `widget_access` 15 分鐘，綁 bot / Origin / visitor |
| LINE | Channel secret 簽章 | LINE 平台 | 每則 webhook 驗簽 |

機器票只能進入宣告了 scope 的端點；拿機器票打後台管理端點一律 `403 insufficient_scope`。

## 2. 取得 API key

由租戶管理員（`tenant_admin`）在後台 **API 金鑰** 頁建立，或呼叫：

```http
POST /api/v1/api-keys
Authorization: Bearer <tenant_admin 的 access token>
Content-Type: application/json

{
  "name": "看板 WebView",
  "description": "門市看板嵌入",
  "scopes": ["chat:send", "chat:history:read"],
  "allowed_bot_ids": ["<bot_id>"],      // 空陣列 = 該租戶所有 bot
  "expires_at": "2027-01-01T00:00:00Z"  // 可省略
}
```

回應（`client_secret` **只出現這一次**，之後只看得到前綴）：

```json
{
  "id": "…", "client_id": "…", "client_secret": "ark_prod_…",
  "secret_prefix": "ark_prod_Ab1", "scopes": ["chat:send", "chat:history:read"],
  "allowed_bot_ids": ["…"], "expires_at": "…", "is_active": true
}
```

- `client_secret` 格式 `ark_<env>_<32 碼>`（env = dev | uat | prod），伺服器只存雜湊。
- 撤銷：`DELETE /api/v1/api-keys/{id}`（已發出的 access token 立即失效）。
- 建立 / 撤銷都寫入稽核紀錄（後台「稽核紀錄」頁可查）。

## 3. 換票（OAuth2 client_credentials）

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>",
  "scope": "chat:send chat:history:read"   // 可省略 = key 的全部 scopes
}
```

回應：

```json
{ "access_token": "eyJ…", "token_type": "Bearer", "expires_in": 900, "scope": "chat:send chat:history:read" }
```

| 狀態碼 | `detail` | 說明 |
|--------|----------|------|
| 400 | `unsupported_grant_type` | grant_type 不是 `client_credentials` |
| 401 | `invalid_client` | client 不存在 / secret 錯 / 已撤銷 / 已過期（刻意同一訊息） |
| 403 | `invalid_scope` | 要求的 scope 超出 key 範圍 |
| 429 | — | `auth` 群組速率限制（預設 10 次/分/IP） |

票內 claims：`iss`、`aud=agentic-rag-api`、`sub=client_id`、`type=api_access`、`tenant_id`、`scopes`、`bot_ids`、`ver`、`jti`、`iat`、`exp`。**不要**自行解析或信任票內容做授權；伺服器每個請求都會驗 `ver` 與 key 狀態。

## 4. 呼叫聊天 API

```http
POST /api/v1/agent/chat
Authorization: Bearer <access_token>
Content-Type: application/json

{ "message": "請問退貨流程？", "bot_id": "<bot_id>", "conversation_id": null }
```

- `bot_id` 必須在 key 的 `allowed_bot_ids` 內（未限制則可用該租戶任一 bot）。
- `conversation_id` 可由客戶端自帶（延續對話）；伺服器一律以票內 tenant 查詢，跨租戶回 404。
- 串流：`POST /api/v1/agent/chat/stream`（SSE），需要 `chat:stream`。

## 5. Scopes 對照

| Scope | 端點 |
|-------|------|
| `chat:send` | `POST /api/v1/agent/chat` |
| `chat:stream` | `POST /api/v1/agent/chat/stream` |
| `chat:history:read` | `GET /api/v1/conversations`、`GET /api/v1/conversations/{id}` |
| `feedback:write` | `POST /api/v1/feedback` |
| `bots:read` | `GET /api/v1/bots`、`GET /api/v1/bots/{id}` |
| `kb:read` / `kb:write` | 保留名稱，尚未開放 |

scope 不符：`403 {"detail": "insufficient_scope"}`；票過期 / 撤銷：`401`。

## 6. 服務間（Cloud Run IAM）

跨專案由另一個 Cloud Run 服務呼叫時，Cloud Run 的 IAM ID token 放 `X-Serverless-Authorization`，本平台的 API 票留在 `Authorization`；兩者互不干擾。

## 7. 常見錯誤碼

| 狀態碼 | 情境 |
|--------|------|
| 401 `Invalid or expired token` | access token 過期 / 簽章錯 → 重新換票 |
| 401 `Invalid or revoked API credentials` | key 已撤銷或 `ver` 不符 → 重新換票；仍 401 代表 key 已撤銷 |
| 403 `insufficient_scope` | scope 不足、bot 不在範圍、或拿機器票打管理端點 |
| 404 | bot / 對話不屬於票內租戶 |
| 429 | 速率限制（`Retry-After`） |

## 8. 安全建議

- secret 只在建立時出現一次；請放入密鑰管理服務，不要寫進前端或版本控制。
- 一個串接系統一把 key；不同 bot 用 `allowed_bot_ids` 切開。
- access token 15 分鐘到期屬設計預期；請在 401 時自動換票，不要快取超過 `expires_in`。
