# TDD 工作流程

引導完成一個完整的 TDD 紅綠重構循環。自動判斷後端（pytest）或前端（Vitest）。

## 使用方式

```
/tdd <元件/Use Case/功能名稱>
```

## 範例

```
/tdd QueryKnowledgeUseCase
/tdd ChatInput component
/tdd useConversation hook
/tdd TenantService create_tenant
```

## 流程

根據 `$ARGUMENTS` 指定的功能名稱，執行以下步驟：

### 步驟一：分析需求

1. 判斷歸屬：
   - Python class / Use Case / Service → 後端 TDD（`apps/backend/`）
   - React component / hook → 前端 TDD（`apps/frontend/`）
2. 若是既有元件，閱讀原始碼了解現有實作
3. 列出需要測試的場景

### 步驟二：撰寫測試（紅燈）

#### 後端

```bash
cd apps/backend && uv run python -m pytest tests/unit/<path> -v --tb=short
```

#### 前端

```bash
cd apps/frontend && npx vitest run <path> --reporter=verbose
```

確認失敗原因是功能未實作（非語法錯誤）。

### 步驟三：實作功能（綠燈）

1. 撰寫最少量的程式碼使測試通過
2. 執行測試確認通過

### 步驟四：重構

1. 改善程式碼結構，消除重複
2. 執行測試確認仍然通過
3. 檢查是否符合 DDD 分層（後端）或 Next.js 慣例（前端）

### 步驟五：循環

1. 回到步驟二，處理下一個測試場景
2. 重複直到所有場景覆蓋完成

### 步驟六：完成報告

輸出完成摘要：
- 建立的檔案列表
- 測試場景數量
- 覆蓋率（若可計算）
- 下一步建議
