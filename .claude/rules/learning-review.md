---
paths:
  - "apps/backend/src/**/*.py"
  - "apps/frontend/src/**/*.ts"
  - "apps/frontend/src/**/*.tsx"
  - "docs/**"
---

# 任務完成後：架構學習與隱憂分析（Learning Review）

> **目的**：每次任務完成後，主動進行技術深度分析，幫助開發者持續提升架構與設計能力。

## 觸發時機

每當一個**非 trivial 任務完成**（功能開發、Bug 修復、重構）後，在交付結果的同時附上一段 **「架構學習筆記」**。

## 非 Trivial 任務判定基準

滿足**任一條件**即為非 trivial，需產出學習筆記：

| 維度 | Trivial（不需筆記） | Non-Trivial（需要筆記） |
|------|---------------------|------------------------|
| 檔案數 | 1-3 個檔案 | 4+ 個檔案 |
| DDD 層數 | 單層變更 | 跨 2+ 層（如 Domain + Infrastructure） |
| 設計模式 | 無新模式引入 | 用了新的 Pattern |
| 測試 | 無新 scenario | 新增 BDD scenario |
| 前後端 | 單端變更 | 前後端都動 |

> **口訣：跨層或跨端，就要寫筆記。**

## 筆記持久化

- 所有學習筆記**必須追加**至 `docs/architecture-journal.md`
- 格式：每則筆記包含「Sprint 來源 → 主題 → 做得好 → 潛在隱憂 → 延伸學習」
- 新筆記插入在目錄下方、既有筆記上方（最新在最前）
- 同步更新目錄（Table of Contents）區塊

## 分析維度（依相關性挑選，不必每次全部覆蓋）

| 維度 | 分析內容 |
|------|----------|
| **Design Patterns** | 本次實作用了哪些模式？是否有更合適的替代模式？常見誤用警示 |
| **DDD 戰術設計** | Aggregate 邊界是否合理？Domain Event 是否該引入？Value Object vs Entity 判斷 |
| **System Design** | 若此功能要支撐 10x/100x 流量，架構瓶頸在哪？需要哪些改動？ |
| **微服務 / 分散式** | 當前 monolith 的哪些部分未來拆分時會痛？CAP 取捨、資料一致性風險 |
| **高併發場景** | Race condition、冪等性、樂觀鎖 / 悲觀鎖、Queue-based 解耦是否需要？ |
| **Design System / UI** | 元件抽象層級、Token 體系一致性、Accessibility 缺口、響應式斷點策略 |
| **可觀測性** | Logging / Tracing / Metrics 是否足夠？告警該設在哪？ |
| **安全隱憂** | 本次變更是否引入新的攻擊面？OWASP Top 10 對照檢查 |

## 輸出格式

```markdown
### 架構學習筆記

**本次相關主題**：[例：Repository Pattern、CQRS、租戶隔離]

#### 做得好的地方
- ...

#### 潛在隱憂
- [隱憂描述] → [建議改善方向] → [優先級：低/中/高]

#### 延伸學習
- [概念名稱]：[一句話解釋為什麼跟本次任務相關]
- 若想深入：[推薦搜尋關鍵字或經典參考資料名稱]

#### 如果沒有明顯隱憂
主動挑一個與本次任務最相關的進階主題進行簡短教學（3-5 段），並提出一個思考題與開發者討論。
```

## 深度等級（依任務複雜度調整）

| 任務規模 | 學習筆記深度 |
|----------|-------------|
| 小型修復 / 單檔變更 | 1-2 句提示，或標註「無特別隱憂」 |
| 中型功能 / 跨層變更 | 挑 2-3 個維度分析，附延伸學習 |
| 大型功能 / 架構變更 | 完整分析 + 討論題 + 替代方案比較 |

## 六階段合規清單（計畫與實作必須遵循）

> **目的**：確保 AI 撰寫的計畫完整涵蓋 CLAUDE.md 定義的 DDD + BDD + TDD 方法論與交付流程。
> 計畫的最後一個 section 必須是本清單的對照結果。

### 設計階段（計畫中必須體現）

- [ ] **Stage 1 — DDD 設計**：確認限界上下文歸屬 + DDD 4 層檔案落點（Domain → Application → Infrastructure → Interfaces）
- [ ] **Stage 2 — BDD 行為規格**：列出 `.feature` 檔案及 Scenario，**先於實作代碼定義**
- [ ] **Stage 3 — TDD 紅燈測試**：列出 Step Definition 檔案，執行順序為「先寫失敗測試 → 再寫實作代碼」

### 實作階段（執行時必須遵循）

- [ ] **Stage 4 — DDD 實作順序**：後端 Domain Entity → Application Use Case → Infrastructure Impl → Interfaces Router；前端 Type → Hook → Component → Page

### 交付階段（完成後必須執行）

- [ ] 全量測試通過（`make test` 或對應指令）
- [ ] Lint 通過（`make lint` 或對應指令）
- [ ] Git commit — Conventional Commits 格式，含 `Refs #N` 或 `Closes #N`
- [ ] **架構學習筆記**（若 non-trivial）— 追加至 `docs/architecture-journal.md`
- [ ] **SPRINT_TODOLIST.md 同步**（若有狀態變更）— 標記 ✅ 並 commit
- [ ] **GitHub Issue 更新**（若有關聯 Issue）— 留 comment 或 close

> **口訣：DDD 定位 → BDD 先寫 → TDD 紅燈 → 實作 → 過清單交付。跳階段 = 違規。**
