---
name: Project Deployment Phase（多環境）
description: 每個部署環境獨立的階段旗標。Claude 依此判斷對該環境執行 migration / DDL / 直連 DB 是否允許。切換任一環境需 Larry 明確批准。
---

# Environment Phase Matrix

| Environment | Phase | Claude 可連該 DB 執行 DDL | 連線方式 |
|-------------|-------|--------------------------|---------|
| `local-docker` | `dev` | ✅（走五步流程）| `docker exec agentic-rag-db psql ...` |
| `dev-vm` | `dev` | ✅（走五步流程 + Larry 授權） | `gcloud compute ssh db-services ... + docker exec agentic-rag-db psql` |
| `staging` | *（未建立）* | - | - |
| `production` | *（未建立）* | - | - |

**當前主要狀態**：
- `local-docker` 已套 `add_message_structured_content.sql` + 建立 `_applied_migrations` 表
- `dev-vm`（Cloud Run 後端連的 DB，推測）：⚠️ **尚未套 `add_message_structured_content.sql`** → 導致 Cloud Run `/conversations/{id}` API 500

**切換記錄**：
- 2026-04-17 — 初始化為多環境 matrix。發現 Cloud Run backend 連 dev-vm，該 DB migration 未同步，列為待處理。

---

## Phase 定義

| Phase | 語意 | Claude 權限 |
|-------|------|------------|
| `dev` | 個人開發 / 內部測試（無外部租戶） | ✅ 可執行 DDL（每次都要 Larry 口頭/書面授權） |
| `pre-prod` | UAT / staging / 有外部測試租戶 | ❌ 禁止直連，只產出 SQL 檔由 Larry / CI 套用 |
| `production` | 正式環境，有實際商業流量 | ❌ 禁止直連，所有 DDL 走 CI/CD pipeline |

## 執行 Migration 的決策流程

1. Larry 或 Claude **明確指定目標環境**（例：「套到 dev-vm」）
2. Claude 讀本檔該環境的 `Phase`
3. 若 `Phase = dev` → 走 `migration-workflow.md` 五步流程（preview → 授權 → 執行 → 驗證 → 記錄 INSERT 到**該環境的 `_applied_migrations`**）
4. 若 `Phase ∈ {pre-prod, production}` → **拒絕執行**，只能產出 SQL 檔 + 更新 `infra/schema.sql`
5. 多環境不一致是常態，Claude 不得假設「local 套過就等於 dev-vm 套過」

## 每個 DB 獨立追蹤

每個環境的 DB 各自維護一份 `_applied_migrations` 表。
- `local-docker` 的 `_applied_migrations` ≠ `dev-vm` 的 `_applied_migrations`
- Migration 執行完的 INSERT 紀錄只寫到「當次執行的那個 DB」，不跨環境同步
- Larry / CI 自行決定哪些 migration 要套到哪個環境

## 切換規則

- **只能由 Larry 明確宣告切換環境 phase**（改本檔案或口頭指示）
- Claude 不得主動修改此檔，包括「推測 staging 已建立」等自作主張
- 新增環境（如首次建立 staging）時 Larry 需：補該環境連線指令 + 設定 phase + 切換記錄加一行
