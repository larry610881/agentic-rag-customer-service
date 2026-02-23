# UI 元件強化

對指定的前端元件套用設計系統 tokens，加入動畫、深度、微互動，提升視覺質感。

## 使用方式

```
/ui-enhance <元件路徑或 PascalCase 名稱>
```

## 範例

```
/ui-enhance KnowledgeBaseCard
/ui-enhance apps/frontend/src/features/chat/components/MessageBubble.tsx
/ui-enhance ChatInput
```

## 流程

根據 `$ARGUMENTS` 指定的元件，執行以下步驟：

### 步驟一：定位元件

1. 若 `$ARGUMENTS` 是檔案路徑，直接讀取
2. 若是 PascalCase 名稱，搜尋 `apps/frontend/src/` 下的匹配檔案：
   ```bash
   # 搜尋元件檔案
   ```
   使用 Glob 搜尋 `apps/frontend/src/**/${name}.tsx`
3. 若找到多個，列出讓使用者確認

### 步驟二：分析缺漏

讀取元件程式碼，對照 **9 項檢查清單**逐項評估：

| # | 項目 | 檢查內容 |
|---|------|---------|
| 1 | Hover | 是否有 hover 回饋（scale / shadow / bg 變化） |
| 2 | Focus | 是否有 `focus-visible:ring-*` |
| 3 | Loading | 是否處理 loading 狀態（skeleton / spinner） |
| 4 | Disabled | 是否處理 disabled 狀態 |
| 5 | 入場動畫 | 是否有 framer-motion 入場 |
| 6 | 退場動畫 | 是否有 AnimatePresence + exit |
| 7 | Dark Mode | shadow 是否搭配 border、色彩是否用 token |
| 8 | Shadow | 是否按 hierarchy 正確分配 |
| 9 | 間距 | padding / gap 是否一致 |

### 步驟三：讀取設計系統 tokens

讀取 `.claude/rules/ui-design-system.md`，取得：
- Shadow hierarchy 對照表
- Animation duration / easing tokens
- Hover / Focus / Loading patterns
- framer-motion 慣例與 code snippets

### 步驟四：套用強化

依據分析結果進行修改：

1. **Import framer-motion**：在檔案頂部加入 `import { motion, AnimatePresence } from 'framer-motion'`
2. **加入 `'use client'`**：若檔案尚未有，在第一行加入
3. **入場動畫**：根據元件類型選擇 slide-up / blur-fade / scale-in
4. **Hover 效果**：卡片 → `hover:scale-[1.02] hover:shadow-md`；按鈕 → `active:scale-95`
5. **Shadow 層次**：依據元件在頁面中的視覺層級分配 shadow level
6. **Loading 狀態**：若元件有 data fetching，加入 Skeleton 或 Spinner
7. **Transition**：所有狀態變化加上 `transition-all duration-200`

### 步驟五：驗證

1. 確認 `'use client'` 已加（若用了 framer-motion / hooks）
2. 確認 dark mode 效果正常（shadow + border、色彩 token）
3. 確認無 `!important`、inline style、hardcode 色值
4. 執行既有測試確認無破壞：
   ```bash
   cd apps/frontend && npx vitest run --passWithNoTests
   ```

### 步驟六：輸出報告

```
## UI 強化報告 — [元件名稱]

### 分析結果
| 項目 | 原狀態 | 強化後 |
|------|--------|--------|
| Hover | ❌/✅ | ✅ 描述 |
| Focus | ❌/✅ | ✅ 描述 |
| Loading | ❌/✅ | ✅ 描述 |
| Disabled | ❌/✅ | ✅ 描述 |
| 入場動畫 | ❌/✅ | ✅ 描述 |
| 退場動畫 | ❌/✅ | ✅ 描述 |
| Dark Mode | ❌/✅ | ✅ 描述 |
| Shadow | ❌/✅ | ✅ 描述 |
| 間距 | ❌/✅ | ✅ 描述 |

### 變更摘要
| 檔案 | 動作 | 描述 |
|------|------|------|
| `path/Component.tsx` | 修改 | 新增動畫 + hover + shadow |

### 測試結果
- ✅ vitest：N tests passed
- ✅ 無 TypeScript 錯誤
```
