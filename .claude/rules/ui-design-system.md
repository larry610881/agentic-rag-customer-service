---
paths:
  - "apps/frontend/**/*.tsx"
---

# UI Design System — Tokens & Conventions

本規範定義前端元件的視覺一致性 tokens，供 `ui-designer` agent 與 `/ui-enhance` skill 參考。

---

## Shadow Hierarchy（6 級）

| Level | Tailwind Class | 用途 |
|-------|---------------|------|
| 0 | `shadow-none` | 平面元素 |
| 1 | `shadow-sm` | 輸入框、小卡片 |
| 2 | `shadow` | 一般卡片、面板 |
| 3 | `shadow-md` | 浮動卡片、Dropdown |
| 4 | `shadow-lg` | Modal、Popover |
| 5 | `shadow-xl` | Toast、最頂層 |
| 6 | `shadow-2xl` | 極特殊場景（慎用） |

### Hover 提升規則

- 卡片 hover：從當前 level 提升 **1-2 級**（如 `shadow` → `shadow-md`）
- 搭配 `transition-shadow duration-200`

---

## Animation Tokens

### Duration

| Token | 時間 | 用途 |
|-------|------|------|
| fast | `150ms` / `duration-150` | hover、focus、toggle |
| normal | `300ms` / `duration-300` | 入場、展開、頁面切換 |
| slow | `500ms` / `duration-500` | 複雜編排、stagger parent |

### Easing Curves

| Token | Tailwind | framer-motion | 用途 |
|-------|----------|--------------|------|
| ease-out | `ease-out` | `[0, 0, 0.2, 1]` | 入場動畫 |
| ease-in | `ease-in` | `[0.4, 0, 1, 1]` | 退場動畫 |
| ease-in-out | `ease-in-out` | `[0.4, 0, 0.2, 1]` | 持續狀態變化 |
| spring | — | `{ type: "spring", stiffness: 300, damping: 24 }` | 彈性回饋 |

---

## Hover Patterns

| 元素 | 效果 | 實作 |
|------|------|------|
| 卡片 | scale + shadow 提升 | `hover:scale-[1.02] hover:shadow-md transition-all duration-200` |
| 按鈕 | 按下縮放 | `active:scale-95 transition-transform duration-150` |
| 列表項 | 背景高亮 | `hover:bg-muted/50 transition-colors duration-150` |
| 圖示按鈕 | 放大 | `hover:scale-110 transition-transform duration-150` |
| 連結 | 底線滑入 | `hover:underline underline-offset-4` |

---

## Loading Patterns

| 模式 | 實作 |
|------|------|
| Skeleton | `animate-pulse bg-muted rounded` |
| Spinner | `motion.div` + `animate={{ rotate: 360 }}` + `transition={{ repeat: Infinity, duration: 1 }}` |
| Progress | `bg-primary` + shimmer gradient animation |
| Dots | 3 個 `motion.span` + `staggerChildren: 0.15` |

---

## Focus Patterns

```
focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:outline-none transition-shadow duration-150
```

- 所有互動元素必須有可見的 focus indicator
- 使用 `focus-visible`（非 `focus`）避免 click 時觸發

---

## Disabled Patterns

```
disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none
```

---

## Entry Animations（framer-motion）

### fade-in

```tsx
initial={{ opacity: 0 }}
animate={{ opacity: 1 }}
transition={{ duration: 0.3 }}
```

### slide-up

```tsx
initial={{ opacity: 0, y: 20 }}
animate={{ opacity: 1, y: 0 }}
transition={{ duration: 0.3, ease: [0, 0, 0.2, 1] }}
```

### blur-fade

```tsx
initial={{ opacity: 0, filter: "blur(4px)" }}
animate={{ opacity: 1, filter: "blur(0px)" }}
transition={{ duration: 0.3 }}
```

### scale-in

```tsx
initial={{ opacity: 0, scale: 0.95 }}
animate={{ opacity: 1, scale: 1 }}
transition={{ duration: 0.2, ease: [0, 0, 0.2, 1] }}
```

### stagger list

```tsx
// Parent
<motion.div variants={{ show: { transition: { staggerChildren: 0.05 } } }} initial="hidden" animate="show">
  {items.map(item => <motion.div key={item.id} variants={itemVariants} />)}
</motion.div>

// Child variant
const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0 },
};
```

---

## 色彩規則

| Token | 用途 | 禁止 |
|-------|------|------|
| `primary` | 主要操作（CTA 按鈕、active 狀態） | 大面積背景 |
| `secondary` | 次要操作 | — |
| `muted` | 背景、disabled、placeholder | 主要文字 |
| `accent` | 強調標籤、badge | — |
| `destructive` | 刪除、錯誤 | 非破壞性操作 |

- **禁止 hardcode 色值**（如 `text-[#333]`）→ 一律使用 CSS 變數 token
- 色彩透明度使用 `/` 語法（如 `bg-primary/10`）

---

## Dark Mode 規則

- 所有視覺效果必須同時考慮 light / dark 模式
- Shadow 在 dark mode 下效果弱 → 搭配 `border` 補強深度
- 使用 `dark:` variant 或 CSS 變數自動適配
- 測試時切換 dark mode 確認效果

---

## 禁止事項

| 禁止 | 原因 | 替代方案 |
|------|------|---------|
| `!important` | 破壞 cascade | 提升 specificity 或重構 |
| `style={{ }}` inline | 不可被 theme 覆蓋 | Tailwind class |
| hardcode 色值 `#xxx` / `rgb()` | 無法跟隨主題 | CSS 變數 token |
| 純裝飾性動畫（無功能意義） | 分散注意力 | 移除 |
| 修改 `components/ui/` 原始元件 | shadcn/ui 升級會覆蓋 | 包裝新元件 |
| `animate-*` 無 `prefers-reduced-motion` 考量 | 無障礙 | `motion-safe:animate-*` |

---

## framer-motion 慣例

1. 使用 framer-motion 的元件檔案頂部必須加 `'use client'`
2. 退場動畫使用 `AnimatePresence`，`exit` 時間 = `animate` 的 **70%**
3. 列表動畫使用 `variants` + `staggerChildren`，避免逐一設定
4. `layoutId` 用於跨元件的共享佈局動畫
5. 避免在大量 DOM 元素上套用 motion（超過 50 個時改用 CSS animation）
