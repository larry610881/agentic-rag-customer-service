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
- 相關的 work item 以 `Fixes #<work item id>` 格式關聯（Azure Repos 語法）

## Azure Boards 工作項目管理

> 2026-09-24 起工作項目一律開在 Azure Boards（組織 `PIC-DevOps`、專案 `檯帳系列-平台POC`、流程範本 **PIC_AGILE**）。
> GitHub Issues 已停用；舊編號對照見 `docs/github-issue-migration-map.md`。

### 生命週期

1. **建立時機**：功能計畫確認後、開發開始前
2. **類型**：
   | 情境 | 類型 |
   |---|---|
   | 新功能 | `User Story` |
   | 缺陷修復 | `Bug`（重現步驟寫在 Repro Steps） |
   | 重構 / 測試 / 基礎建設 / CI | `Task` |
   | 跨多張單的大計畫 | `Feature`（其他單掛在底下） |
3. **必要欄位**：
   - Title：簡短描述做什麼（不加 `feat(scope):` 前綴，那是 commit 格式）
   - Description：Summary + Sub-tasks（checkbox）+ Acceptance Criteria
   - Assigned To：`p10359945@pic.net.tw`
   - Tags：`refactor` / `test` / `infra` / `security` 等補充分類
4. **狀態流轉**（PIC_AGILE）：
   | 狀態 | 時機 |
   |---|---|
   | `New` | 建立 |
   | `Active` | 開始開發 |
   | `Resolved` | 已合進 main，尚未部署（Bug、User Story、Feature 才有） |
   | `Closed` | 已部署上線並驗證 |
   | `Removed` | 決定不做 |
5. **進度更新**：每個階段 / 子任務完成後留言（支援 Markdown）

### CLI

```bash
# 建立（先 az devops login；預設 org / project 已由 az devops configure 設好）
az boards work-item create --type "User Story" --title "<簡短標題>" \
  --description "<HTML 或純文字>" --assigned-to p10359945@pic.net.tw --fields "System.Tags=security"
# 留言
az boards work-item update --id <id> --discussion "E1.3 完成：6 Use Cases"
# 改狀態
az boards work-item update --id <id> --state Resolved
```

注意：`--description` 以 HTML 儲存，Markdown 不會被轉換；需要格式時先轉成 HTML。

### Commit 關聯 work item

- 開發中的 commit：message 末尾加 `#<work item id>`（Azure Repos 會自動連結到該單）
- 最終完成的 commit：`Fixes #<work item id>`
- 舊的 `Refs #N` / `Closes #N`（N < 200）指的是已停用的 GitHub Issue

## 提交前檢查

- 確保 `make lint` 通過
- 確保 `make test` 通過
- 確保沒有提交 `.env` 或敏感檔案
- 使用 `git diff --staged` 確認變更內容
