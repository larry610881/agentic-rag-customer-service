---
paths:
  - "**/*.md"
---

# Mermaid 繪圖規則

## 核心規則

- **禁止使用 ASCII art 畫架構圖、流程圖、時序圖等示意圖**
- 一律使用 ` ```mermaid ` code block 繪製
- 若既有文件中發現 ASCII art 圖表，編輯時順手轉為 Mermaid

## 圖表類型對照

| 用途 | Mermaid 語法 |
|------|-------------|
| 架構圖（上→下） | `graph TD` |
| 流程圖（左→右） | `graph LR` |
| 時序圖 | `sequenceDiagram` |
| 分支決策 | 菱形節點 `{判斷條件}` |

## Mermaid 語法規範

- 中文標籤必須用引號包裹：`A["中文標籤"]`
- 換行使用 `<br>`：`A["第一行<br>第二行"]`
- Node ID 全域不重複，使用有意義的英文命名
- 箭頭統一用 `-->` 或 `-->`（帶文字用 `-->|文字|`）

## 不適用場景（維持原格式）

- YAML / TypeScript / Python 等程式碼 code blocks
- Checklist（`- [ ]` / `- [x]`）
- 成本計算、數值表格
- Terminal output / CLI 範例

## ASCII Box Table 處理

- ASCII box table（`+---+---+` 風格）轉為 **Markdown table**（非 Mermaid）
