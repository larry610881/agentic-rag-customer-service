# README 美化

使用 MCP readme-beautifier 工具分析專案並產生美化的 README.md，同時用 Python diagrams 重新產生架構圖。

## 使用方式

- `/readme` — 完整美化 README + 重新產生架構圖
- `/readme 只更新架構圖` — 只重新產生 Python diagrams 架構圖
- `/readme 只更新文字` — 只美化 README 文字，不重新產生圖片

## 執行步驟

### 步驟 1：產生架構圖

使用 Python diagrams 套件產生系統架構圖：

```bash
cd /home/p10359945/source/repos/agentic-rag-customer-service && uv run --with diagrams python scripts/generate_architecture.py 2>&1
```

- 腳本位置：`scripts/generate_architecture.py`
- 產出位置：`docs/images/architecture_diagrams.png`
- 需要系統安裝 Graphviz（`sudo apt install graphviz` 或 `winget install Graphviz.Graphviz`）
- 若 Graphviz 未安裝導致失敗，提示使用者安裝後重試

### 步驟 2：MCP 分析與素材產生

依序呼叫以下 MCP 工具，收集所有素材：

1. **`analyze_project`** — 分析專案技術堆疊、scripts、目錄結構
2. **`apply_template`** — 套用 `awesome` 模板，語系 `zh-TW`
3. **`generate_badges`** — 產生技術徽章，預設 `for-the-badge` 風格
4. **`generate_toc`** — 產生目錄（Table of Contents）

### 步驟 3：讀取現有 README

讀取現有 `README.md`，了解目前的內容結構，避免遺失已有的自訂內容。

### 步驟 4：整合與排版修正

將 MCP 產出的素材整合為一份完整 README，並**自動修正以下已知排版問題**：

- **架構圖**：使用 `docs/images/architecture_diagrams.png`（Python diagrams 產出），以 `<img>` 標籤置中顯示
- **技術堆疊**：使用 **HTML `<table>` + 小型 badge 併排**，同類技術橫向排列
- **Badge 區域**：頂部 badge 使用 `for-the-badge` 大型樣式，置中排列；技術堆疊表格內用預設小型樣式
- **表格對齊**：確保所有 Markdown 表格欄位寬度合理

### 步驟 5：寫入檔案

將最終結果寫入 `README.md`。

## 架構圖維護

架構圖原始碼在 `scripts/generate_architecture.py`。若架構有變更（新增 Bounded Context、新增外部服務等），應同步更新腳本後重新產生：

```bash
uv run --with diagrams python scripts/generate_architecture.py
```

同時保留 Mermaid 原始碼 `docs/images/architecture.mmd` 作為備用。

## 額外指示

$ARGUMENTS
