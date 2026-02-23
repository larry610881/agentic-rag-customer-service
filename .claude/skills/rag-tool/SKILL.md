# LangGraph Tool 建立

根據指定的 Tool 需求，生成 LangGraph Tool 定義、Domain Interface、Infrastructure 實作、BDD 測試。

## 使用方式

```
/rag-tool <tool-name> <功能描述>
```

## 範例

```
/rag-tool knowledge-search 從知識庫搜尋相關文件
/rag-tool order-query 查詢客戶訂單狀態
/rag-tool product-lookup 查詢商品資訊
/rag-tool faq-search 搜尋常見問題解答
```

## 流程

根據 `$ARGUMENTS` 指定的 Tool 名稱和功能描述，執行以下步驟：

### 步驟一：分析需求

1. 確認 Tool 的輸入/輸出格式
2. 確認 Tool 需要的依賴（Repository / External API）
3. 確認 Tool 是否需要 tenant_id 過濾

### 步驟二：建立 Domain Interface

```python
# apps/backend/src/domain/agent/tools.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ToolInput(BaseModel):
    query: str
    tenant_id: str

class ToolOutput(BaseModel):
    result: str
    sources: list[str]

class ToolInterface(ABC):
    @abstractmethod
    async def execute(self, input: ToolInput) -> ToolOutput: ...
```

### 步驟三：建立 Infrastructure 實作

```python
# apps/backend/src/infrastructure/langgraph/tools/<tool_name>.py
from langchain_core.tools import tool

@tool
def knowledge_search(query: str, tenant_id: str) -> str:
    """從知識庫搜尋相關文件回答客戶問題"""
    # Implementation
```

### 步驟四：建立 BDD Feature

```gherkin
Feature: <Tool 名稱> Tool
    身為 LangGraph Agent
    我需要 <Tool 名稱> 工具
    以便 <功能描述>

    Scenario: 成功執行 Tool
        Given Agent 已載入 <Tool 名稱> Tool
        And 租戶 "T001" 的相關資料已準備
        When Agent 使用 <Tool 名稱> 處理查詢 "<查詢>"
        Then 應回傳正確的結果
        And 結果應只包含租戶 "T001" 的資料
```

### 步驟五：建立 Unit Test

使用 AsyncMock mock 底層依賴，只測 Tool 的邏輯：

```python
scenarios("unit/agent/<tool_name>.feature")

@given("Agent 已載入 <Tool> Tool", target_fixture="context")
def setup_tool():
    mock_repo = AsyncMock()
    mock_repo.search = AsyncMock(return_value=[...])
    tool = KnowledgeSearchTool(repo=mock_repo)
    return {"tool": tool, "mock_repo": mock_repo}
```

### 步驟六：執行測試與報告

```bash
cd apps/backend && uv run python -m pytest tests/unit/agent/ -v --tb=short
```

輸出已建立的檔案列表、Tool 的 description（影響 Agent 選擇準確度）、與其他 Tool 的搭配建議。
