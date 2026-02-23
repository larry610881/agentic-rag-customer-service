# Demo Guide

6 個 Demo 場景操作手冊，每個場景應在 3 分鐘內完成。

## 前置準備

1. 確保所有服務已啟動（`make dev-up`）
2. 已載入種子資料（`make seed-data`）
3. 已設定 LLM Provider（見 [Configuration](./configuration.md)）
4. 取得 JWT Token：

```bash
# 建立租戶
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "Demo Store A", "plan": "free"}'

# 記下 tenant_id，取得 token
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "<tenant_id>"}'

export TOKEN="<access_token>"
```

---

## Demo 1: 上傳商品目錄 → 自動建立知識庫

**展示重點**：RAG Pipeline 文件處理能力

### 步驟

1. 建立知識庫：

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Product Catalog", "description": "商品目錄"}'
```

2. 上傳文件：

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases/<kb_id>/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/seeds/products.csv"
```

3. 查詢處理進度：

```bash
curl http://localhost:8000/api/v1/tasks/<task_id> \
  -H "Authorization: Bearer $TOKEN"
```

**預期結果**：文件上傳後自動進行解析 → 分塊 → 向量化，task status 變為 `completed`。

---

## Demo 2: 客戶詢問商品規格 → AI 基於知識庫回答

**展示重點**：RAG 問答 + 引用來源

### 步驟

1. 發送 RAG 查詢：

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "<kb_id>",
    "query": "有哪些藍牙耳機？價格多少？"
  }'
```

**預期結果**：
- `answer` 包含從知識庫檢索到的商品資訊
- `sources` 列出引用的文件 chunk 與相似度分數

---

## Demo 3: 客戶查詢訂單狀態 → Agent 自動使用工具

**展示重點**：Agentic Tool Use（OrderLookupTool）

### 步驟

1. 透過 Agent Chat 查詢訂單：

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "<kb_id>",
    "message": "我的訂單 ORD-001 目前狀態如何？"
  }'
```

**預期結果**：
- Agent 自動呼叫 `OrderLookupTool` 查詢訂單
- `tool_calls` 顯示使用的工具
- `answer` 包含訂單狀態資訊

---

## Demo 4: 客戶申請退貨 → 多步驟引導 → 建立工單

**展示重點**：多輪 Agentic 工作流（RefundWorker + TicketCreationTool）

### 步驟

1. 發起退貨請求：

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "<kb_id>",
    "message": "我想退貨"
  }'
```

2. 根據 Agent 引導提供資訊（帶入 conversation_id 延續對話）：

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "<kb_id>",
    "message": "訂單編號是 ORD-001，原因是尺寸不合",
    "conversation_id": "<conversation_id>"
  }'
```

**預期結果**：
- Agent 引導使用者提供必要資訊
- 自動建立退貨工單
- 多輪對話歷史完整保留

---

## Demo 5: 租戶隔離驗證

**展示重點**：多租戶資料隔離

### 步驟

1. 建立第二個租戶並取得 Token：

```bash
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "Demo Store B", "plan": "free"}'

curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "<tenant_b_id>"}'

export TOKEN_B="<access_token>"
```

2. 用租戶 B 的 Token 嘗試查詢租戶 A 的知識庫：

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "<tenant_a_kb_id>",
    "query": "商品規格"
  }'
```

**預期結果**：租戶 B 無法存取租戶 A 的知識庫，回傳 404 或空結果。

---

## Demo 6: LINE Bot 對話

**展示重點**：LINE 整合 + 共用 RAG Pipeline

### 前置設定

1. 在 [LINE Developers](https://developers.line.biz/) 建立 Messaging API Channel
2. 設定 `.env`：

```env
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-access-token
LINE_DEFAULT_TENANT_ID=<tenant_id>
LINE_DEFAULT_KB_ID=<kb_id>
```

3. 設定 Webhook URL（可用 ngrok）：`https://your-domain/api/v1/webhook/line`

### 步驟

1. 在 LINE App 中加入你的 Bot 好友
2. 傳送訊息：「有哪些藍牙耳機？」
3. Bot 透過 Agent + RAG Pipeline 回應

**預期結果**：
- LINE Bot 接收訊息
- 經過 Agent 處理 + RAG 檢索
- 回傳包含知識庫內容的回答

---

## 驗證清單

| Demo | 場景 | 通過標準 |
|------|------|----------|
| 1 | 文件上傳 | task status = completed |
| 2 | RAG 問答 | answer 包含知識庫內容 + sources 非空 |
| 3 | 訂單查詢 | tool_calls 包含 OrderLookup |
| 4 | 退貨流程 | 多輪對話 + 工單建立 |
| 5 | 租戶隔離 | 跨租戶無法存取 |
| 6 | LINE Bot | 收到 Bot 回覆 |
