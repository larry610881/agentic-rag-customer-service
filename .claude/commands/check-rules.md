# 檢查規範合規 + 同步 Sprint Todolist

檢查當前程式碼是否符合專案規範，並同步更新 `SPRINT_TODOLIST.md` 的完成狀態。

## 使用方式

- `/check-rules` — 完整掃描：規範合規 + 更新 todolist
- `/check-rules --plan` — 僅檢查計畫變更，更新 todolist
- `/check-rules --verify S0` — 驗證指定 Sprint 的完成狀態

## 執行步驟

### 1. 讀取目前 Sprint Todolist

讀取 `SPRINT_TODOLIST.md`，解析所有 Sprint 任務的目前狀態。

### 2. 掃描專案實際狀態

針對每個 todolist 項目，檢查對應的檔案/功能是否已存在且符合規範：

#### 檔案存在性檢查
- 掃描 `apps/backend/` 和 `apps/frontend/` 確認哪些檔案已建立
- 檢查 BDD Feature 檔案是否存在
- 檢查 step definitions 是否存在
- 檢查 Docker Compose、Makefile 等基礎設施

#### 規範合規檢查
- **DDD 分層**：Domain 是否依賴外層？Application 是否 import Infrastructure？
- **測試隔離**：Unit Test 是否使用 AsyncMock？是否有真實 DB 操作？
- **pytest-bdd**：step definition 是否為 `def`（非 `async def`）？
- **前端**：是否有 `any` 型別？是否使用 `fireEvent`（應用 `userEvent`）？
- **安全**：是否有 hardcoded secrets？是否有 `dangerouslySetInnerHTML`？
- **RAG**：向量搜尋是否有 tenant_id 過濾？Prompt 是否有注入風險？

#### 測試狀態檢查

```bash
# 後端測試（如果存在）
cd apps/backend && uv run python -m pytest tests/ -v --tb=short -q 2>&1

# 前端測試（如果存在）
cd apps/frontend && npx vitest run --reporter=verbose 2>&1
```

### 3. 更新 SPRINT_TODOLIST.md

根據掃描結果，自動更新每個 todolist 項目的狀態：

- 檔案已建立 + 測試通過 → ✅ 完成
- 檔案已建立但測試未通過 → 🔄 進行中
- 被前置任務阻塞 → ❌ 阻塞
- 尚未開始 → ⬜ 待辦

同時更新：
- 進度總覽表的完成率百分比
- 每個 Sprint 的狀態（待辦/進行中/完成）
- 「最後更新」時間戳

### 4. 輸出報告

```markdown
## 規範檢查報告

### 📋 Sprint 進度
| Sprint | 狀態 | 完成率 | 變更 |
|--------|------|--------|------|
| S0 | 🔄 進行中 | 60% | +2 項完成 |
| S1 | ⬜ 待辦 | 0% | 無變更 |

### ⚠️ 規範違規 (X 處)
- `file:line` — [違規類型] 說明

### ✅ 合規項目
- DDD 分層 ✅
- 測試隔離 ✅
- 安全檢查 ✅

### 📝 Todolist 更新
- 新增完成項目: X
- 狀態變更: X
- 已寫入 SPRINT_TODOLIST.md

### 💡 建議下一步
- ...
```

### 5. 提交更新

如果 `SPRINT_TODOLIST.md` 有變更，提示用戶是否要 commit：

```
SPRINT_TODOLIST.md 已更新。是否要 commit？
```
