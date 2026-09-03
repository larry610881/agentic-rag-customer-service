# API Reference

Base URL: `http://localhost:8000/api/v1`

所有需要認證的端點須在 Header 中帶入 `Authorization: Bearer <token>`。

## Health

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | 系統健康檢查 | No |

**Response**
```json
{ "status": "healthy", "database": "connected", "version": "0.1.0" }
```

## Auth

> 憑證模型與 API 模式串接完整說明見 [`api-integration-guide.md`](api-integration-guide.md)。

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/auth/login` | email + 密碼登入，回 access（15 分）+ refresh（7 天） | No |
| POST | `/auth/refresh` | refresh 換票（每次旋轉；重用舊票 → 整組撤銷） | No（票在 body） |
| POST | `/auth/token` | OAuth2 `client_credentials`：API key 換 `api_access` 票 | No（client_secret 在 body） |
| POST | `/auth/register` | 建立使用者（邀請制：system_admin 任意；tenant_admin 只能建自己租戶的 user / tenant_admin） | Yes |
| POST | `/auth/change-password` | 變更密碼（舊 access / refresh 立即失效） | Yes |
| POST | `/api-keys` | 建立租戶 API key（secret 只回一次） | tenant_admin / system_admin |
| GET | `/api-keys` | 列出 API key | tenant_admin / system_admin |
| DELETE | `/api-keys/{id}` | 撤銷 API key | tenant_admin / system_admin |

**POST /auth/login Request**
```json
{ "account": "user@example.com", "password": "..." }
```

**POST /auth/token Request / Response**
```json
{ "grant_type": "client_credentials", "client_id": "...", "client_secret": "ark_prod_...", "scope": "chat:send" }
```
```json
{ "access_token": "eyJ...", "token_type": "Bearer", "expires_in": 900, "scope": "chat:send" }
```

機器票（`api_access`）只能進入宣告了 scope 的端點（`chat:send`、`chat:stream`、
`chat:history:read`、`feedback:write`、`bots:read`），其餘一律 `403 insufficient_scope`。

## Tenant

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/tenants` | 建立租戶 | No |
| GET | `/tenants` | 列出所有租戶 | No |
| GET | `/tenants/{tenant_id}` | 取得租戶詳情 | No |

**POST /tenants Request**
```json
{ "name": "My Store", "plan": "free" }
```

## Knowledge Base

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/knowledge-bases` | 建立知識庫 | Yes |
| GET | `/knowledge-bases` | 列出租戶知識庫 | Yes |

**POST /knowledge-bases Request**
```json
{ "name": "Product Catalog", "description": "商品目錄知識庫" }
```

## Document

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/knowledge-bases/{kb_id}/documents` | 上傳文件（10MB 限制） | Yes |

**Request**: `multipart/form-data` with file field

**Response**
```json
{ "document": { "id": "uuid", "filename": "catalog.pdf" }, "task_id": "uuid" }
```

上傳後會非同步進行文件解析、分塊、向量化。

## Task

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/tasks/{task_id}` | 查詢文件處理進度 | Yes |

**Response**
```json
{ "id": "uuid", "status": "completed", "progress": 100 }
```

## RAG Query

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/rag/query` | RAG 查詢 | Yes |
| POST | `/rag/query/stream` | RAG 查詢（SSE Streaming） | Yes |

**Request**
```json
{
  "knowledge_base_id": "uuid",
  "query": "退貨政策是什麼？",
  "top_k": 5
}
```

**Response**
```json
{
  "answer": "根據知識庫...",
  "sources": [{ "chunk_id": "uuid", "content": "...", "score": 0.95 }],
  "query": "退貨政策是什麼？",
  "usage": { "input_tokens": 150, "output_tokens": 200 }
}
```

## Agent Chat

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/agent/chat` | Agent 對話 | Yes |
| POST | `/agent/chat/stream` | Agent 對話（SSE Streaming） | Yes |

**Request**
```json
{
  "knowledge_base_id": "uuid",
  "message": "我想退貨",
  "conversation_id": "uuid"
}
```

**Response**
```json
{
  "answer": "好的，請提供您的訂單編號...",
  "conversation_id": "uuid",
  "tool_calls": [],
  "sources": [],
  "usage": { "input_tokens": 200, "output_tokens": 150 }
}
```

`conversation_id` 為選填；首次對話不帶會自動建立，後續帶入以延續對話。

## Conversation

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/conversations` | 列出租戶對話 | Yes |
| GET | `/conversations/{conversation_id}` | 取得對話詳情（含歷史訊息） | Yes |

**GET /conversations/{id} Response**
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "messages": [
    { "role": "user", "content": "我想退貨" },
    { "role": "assistant", "content": "好的，請提供訂單編號..." }
  ]
}
```

## Usage

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/usage` | 查詢 Token 用量統計 | Yes |

**Query Parameters**: `start_date` (optional), `end_date` (optional)

**Response**
```json
{
  "tenant_id": "uuid",
  "total_input_tokens": 5000,
  "total_output_tokens": 3000,
  "total_tokens": 8000,
  "total_cost": 0.05,
  "by_model": {},
  "by_request_type": {}
}
```

## LINE Webhook

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/webhook/line` | LINE Bot Webhook | LINE Signature |

需設定 `X-Line-Signature` header，由 LINE Platform 自動帶入。

**Response**
```json
{ "status": "ok" }
```
