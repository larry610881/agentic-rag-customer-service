---
paths:
  - "apps/backend/src/domain/rag/**"
  - "apps/backend/src/domain/knowledge/**"
  - "apps/backend/src/infrastructure/rag/**"
  - "apps/backend/src/infrastructure/qdrant/**"
  - "apps/backend/src/infrastructure/embedding/**"
  - "apps/backend/src/application/rag/**"
  - "apps/backend/src/application/knowledge/**"
---

# RAG Pipeline 開發規範

## RAG 架構概覽

```
使用者查詢 → Embedding → 向量搜尋 (Qdrant) → 文件檢索 → Prompt 組裝 → LLM 回答
                                    ↓
                            tenant_id 過濾（必要）
```

## 核心原則

### 租戶隔離（CRITICAL）
- **所有向量搜尋必須包含 `tenant_id` 過濾條件**
- Qdrant payload filter 必須包含 `tenant_id` 欄位
- 知識庫 CRUD 操作必須驗證 `tenant_id` 歸屬
- 測試必須驗證跨租戶查詢返回空結果

### Prompt 安全
- 使用者輸入不得直接拼入 System Prompt
- 檢索結果注入前必須 sanitize
- System Prompt 與使用者訊息使用 message role 明確分隔

### Embedding 策略
- 使用固定維度的 Embedding model（如 text-embedding-3-small: 1536 維）
- Embedding API key 透過環境變數管理
- 批次處理設定合理的 chunk size 和 rate limit

## DDD 分層

| 概念 | 層級 | 路徑 |
|------|------|------|
| Document Entity | Domain | `domain/knowledge/entity.py` |
| Chunk Value Object | Domain | `domain/knowledge/value_objects.py` |
| KnowledgeRepository Interface | Domain | `domain/knowledge/repository.py` |
| VectorSearchService Interface | Domain | `domain/rag/services.py` |
| UploadDocumentUseCase | Application | `application/knowledge/upload.py` |
| QueryRAGUseCase | Application | `application/rag/query.py` |
| QdrantVectorRepo | Infrastructure | `infrastructure/qdrant/repository.py` |
| EmbeddingService | Infrastructure | `infrastructure/embedding/service.py` |
| LangGraphAgent | Infrastructure | `infrastructure/langgraph/agent.py` |

## RAG BDD 場景模板

### 文件上傳場景

```gherkin
Feature: 知識庫文件上傳 (Knowledge Document Upload)
    身為租戶管理員
    我想要上傳文件到知識庫
    以便 AI 客服能夠參考這些文件回答問題

    Scenario: 成功上傳 PDF 文件
        Given 租戶 "T001" 已建立知識庫
        When 我上傳 PDF 文件 "退貨政策.pdf"
        Then 文件應成功儲存
        And 文件應被分塊並向量化
        And 所有 chunk 應包含 tenant_id "T001"

    Scenario: 上傳不支援的檔案格式
        Given 租戶 "T001" 已建立知識庫
        When 我上傳檔案 "image.exe"
        Then 應回傳格式不支援的錯誤
```

### 向量搜尋場景

```gherkin
Feature: RAG 查詢 (RAG Query)
    身為客戶
    我想要詢問客服問題
    以便快速得到準確的答案

    Scenario: 成功查詢並回傳相關文件
        Given 租戶 "T001" 的知識庫中有退貨政策文件
        When 客戶查詢 "退貨流程是什麼"
        Then 應檢索到相關的知識庫文件
        And 回傳的文件相似度分數應大於 0.7

    Scenario: 租戶隔離驗證
        Given 租戶 "T001" 的知識庫中有退貨政策文件
        And 租戶 "T002" 的知識庫中有物流政策文件
        When 以租戶 "T001" 身份查詢 "物流政策"
        Then 不應回傳租戶 "T002" 的文件

    Scenario: 查詢無結果時的友善回應
        Given 租戶 "T001" 的知識庫為空
        When 客戶查詢 "任何問題"
        Then 應回傳友善的預設回應
        And 回應應提示知識庫尚未建立
```

### LangGraph Agent 場景

```gherkin
Feature: LangGraph Agent 編排 (Agent Orchestration)
    身為系統
    我需要根據客戶查詢選擇正確的 Tool
    以便提供最佳的回答

    Scenario: Agent 選擇 RAG Tool 回答知識庫問題
        Given Agent 已載入 RAG Tool 和 Order Tool
        When 客戶查詢 "退貨政策是什麼"
        Then Agent 應選擇 RAG Tool
        And 應從知識庫檢索相關文件

    Scenario: Agent 選擇 Order Tool 查詢訂單
        Given Agent 已載入 RAG Tool 和 Order Tool
        When 客戶查詢 "我的訂單 ORD-001 目前狀態"
        Then Agent 應選擇 Order Tool
        And 應查詢訂單系統取得狀態
```

## Embedding 測試策略

### Unit Test：Mock Embedding API
```python
mock_embedding = AsyncMock()
mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 1536)
mock_embedding.embed_documents = AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536])
```

### Integration Test：固定向量或 Mock Server
- 使用預先計算好的固定向量進行搜尋測試
- 或使用 Mock Embedding Server 回傳確定性結果

## Qdrant 測試策略

### Unit Test：完全 Mock
```python
mock_qdrant = AsyncMock()
mock_qdrant.search = AsyncMock(return_value=[
    SimpleNamespace(id="1", score=0.95, payload={"content": "退貨政策", "tenant_id": "T001"}),
])
```

### Integration Test：Docker Qdrant
- 使用 Docker Compose 中的 Qdrant 實例
- 每個測試前清空 collection
- 使用 testcontainer（可選）

## LangGraph 測試策略

### Unit Test：Mock 節點
- 每個 Tool 獨立測試（Mock LLM 回應）
- Graph 編排邏輯獨立測試（Mock Tool 結果）

### Integration Test：真實 Graph
- 使用 Mock LLM（固定回應）+ 真實 Tool + 真實 DB
- 驗證 Graph 的節點轉換和狀態管理
