---
paths:
  - "**/*"
---

# Git 工作流程規範

## Commit 訊息格式（Conventional Commits）

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Type 類別

| Type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 錯誤修復 |
| `test` | 新增或修改測試 |
| `refactor` | 重構（不改變功能） |
| `docs` | 文件變更 |
| `chore` | 建置工具、設定變更 |
| `style` | 程式碼格式（不影響邏輯） |
| `perf` | 效能改善 |

### Scope 慣例（Monorepo）

| Scope | 用途 |
|-------|------|
| `backend` | 後端應用 |
| `frontend` | 前端應用 |
| `rag` | RAG Pipeline 相關 |
| `agent` | LangGraph Agent 相關 |
| `infra` | 基礎設施 / Docker |
| `monorepo` | 跨 app 共用設定 |

### 範例

```
feat(backend): 新增租戶知識庫上傳 API
feat(rag): 實作文件分塊與向量化 Pipeline
fix(frontend): 修復對話視窗捲動定位問題
test(backend): 新增 RAG 查詢 BDD 測試
refactor(agent): 重構 LangGraph Tool 注入機制
chore(infra): 更新 Qdrant Docker Compose 設定
```

## 分支命名

```
feature/<scope>/<功能描述>    # 新功能
fix/<scope>/<問題描述>        # 錯誤修復
test/<scope>/<測試描述>       # 測試相關
refactor/<scope>/<描述>       # 重構
```

範例：
- `feature/rag/document-chunking`
- `fix/backend/tenant-isolation-query`
- `test/frontend/conversation-e2e`

## PR 規範

- PR 標題遵循 Conventional Commits 格式
- PR 必須通過所有測試與 lint 檢查
- PR 描述需包含：變更摘要、測試計畫
- 相關的 Issue 以 `Closes #123` 格式關聯

## GitHub Issue 管理

### Issue 生命週期

1. **建立時機**：功能計畫確認後、開發開始前
2. **必要欄位**：
   - Title：`<type>(<scope>): <description>`（與 commit 格式一致）
   - Body：Summary + Sub-tasks (checkbox) + Acceptance Criteria
   - Labels：`enhancement` / `bug` / `refactor`
3. **進度更新**：每個階段/子任務完成後留 comment
4. **關閉**：開發完成 + 測試通過後 `gh issue close <number> --reason completed`

### Commit 關聯 Issue

- 開發中的 commit：message 末尾加 `Refs #<issue-number>`
- 最終完成的 commit：message 末尾加 `Closes #<issue-number>`

## 提交前檢查

- 確保 `make lint` 通過
- 確保 `make test` 通過
- 確保沒有提交 `.env` 或敏感檔案
- 使用 `git diff --staged` 確認變更內容
