# Agentic RAG Customer Service — 開發規範

## 專案概述

Monorepo 架構的 RAG AI Agent 電商客服平台。採用 DDD + TDD + BDD 開發方法論，後端 Python FastAPI + LangGraph，前端 Next.js App Router。

> DDD 架構紅線、測試規則、安全規範等詳見 `.claude/rules/` 下的自動套用規則。

## 限界上下文（Bounded Contexts）

| 上下文 | 路徑 | 職責 |
|--------|------|------|
| Tenant | `domain/tenant/` | 多租戶管理、租戶隔離 |
| Knowledge | `domain/knowledge/` | 知識庫管理、文件上傳與分塊 |
| RAG | `domain/rag/` | 檢索增強生成、向量搜尋、Prompt 組裝 |
| Conversation | `domain/conversation/` | 對話管理、對話歷史 |
| Agent | `domain/agent/` | LangGraph Agent 編排、Tool 管理 |

## 開發工作流（六階段，不可跳過）

### Stage 0：Issue 建立
- 計畫確認後，使用 `gh issue create` 建立 GitHub Issue
- Issue 內容：Summary + Sub-tasks（checkbox） + Acceptance Criteria
- Issue label：`enhancement`（功能）/ `bug`（修復）/ `refactor`（重構）
- 後續 commit message 加上 `Refs #<issue-number>`

### Stage 1：設計與架構
- 確認限界上下文歸屬
- 規劃 DDD 4 層的檔案落點（Domain → Application → Infrastructure → Interfaces）
- 若涉及 RAG，規劃 LangGraph 節點與 Tool
- 重大決策記錄 ADR

### Stage 2：BDD 行為規格
- **先寫 `.feature` 再寫任何程式碼**
- Gherkin 關鍵字維持英文，描述內容使用繁體中文
- 後端：`apps/backend/tests/features/`
- 前端 E2E：`apps/frontend/e2e/features/`

### Stage 3：TDD 測試
- 根據 `.feature` 撰寫會失敗的測試（紅燈）
- **禁止在沒有對應測試的情況下開始實作功能代碼**
- 後端 Unit Test 必須用 `AsyncMock` mock Repository，禁止真實 DB
- 前端 Unit Test 必須用 `vi.mock()` 隔離依賴

### Stage 4：規範化實作
- **後端** DDD 4-Layer 順序：Domain Entity → Application Use Case → Infrastructure Impl → Interfaces Router
- **前端** 元件開發順序：Type → Hook → Component → Page
- **品質反思（非 trivial 變更）**：實作完成後自問「是否有更優雅的解法？」，若有則重構；簡單明確的修改不需額外反思

### Stage 5：驗證與交付
- 全量測試通過：`make test`
- 無 lint 錯誤：`make lint`
- 覆蓋率 ≥ 80%
- 已 commit 並 push
- **Close Issue**：`gh issue close <number> --reason completed`

## Bug Fix 工作流（不可省略測試）

1. **重現**：確認 Bug 的觸發條件與預期行為
2. **寫 Regression Test**：先寫一個會 FAIL 的測試重現 Bug
3. **修復**：修改程式碼直到 regression test 通過
4. **驗證**：全量測試通過 + 覆蓋率不下降

> **原則：每個 Bug fix 都必須留下 regression test。**
> **Root Cause 原則：必須找到根因再修復，禁止臨時繞過或表面修補。若修復方式感覺 hacky，退一步重新分析問題本質。**

## Sprint 管理

- **開發計畫**：`DEVELOPMENT_PLAN.md` — 完整的 S0-S7 Sprint 規劃
- **進度追蹤**：`SPRINT_TODOLIST.md` — 所有 Sprint 任務的 checkbox 追蹤
- **合規檢查**：`/sprint-sync` — 掃描規範合規 + 同步更新 todolist

### Todolist 同步規則

以下情境**必須**同步更新 `SPRINT_TODOLIST.md`：
1. **任務完成時** — 將對應項目標記為 ✅
2. **計畫變更時** — 新增/移除/修改 todolist 項目
3. **開發驗證時** — 執行 `/sprint-sync` 自動掃描並更新
4. **Session 結束前** — Stop hook 會提醒檢查 todolist 是否已同步

### Issue 進度同步規則

1. **計畫完成後** — 建立 GitHub Issue（Sub-tasks 用 checkbox）
2. **每個子任務完成後** — 在 Issue 留 comment 更新進度（如 `E1.3 完成：6 Use Cases`）
3. **全部完成後** — Close Issue + 更新 SPRINT_TODOLIST.md

## Agent Team 協調

涉及前後端的功能，Lead 必須建立 3 層 Task 結構：

```
Task: 後端實作  ──┐
                   ├──→ Task: E2E 整合測試 (addBlockedBy: 前兩者)
Task: 前端實作  ──┘
```

**判斷口訣：能 fire-and-forget 就用 Subagent，需要等待或對話就用 Teams。**

## 架構學習筆記

完成非 trivial 任務後，依照 `.claude/rules/learning-review.md` 撰寫架構筆記至 `docs/architecture-journal.md`。
