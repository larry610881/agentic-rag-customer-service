---
name: Project Deployment Phase（多環境）
description: 每個部署環境獨立的階段旗標。Claude 依此判斷對該環境執行 migration / DDL / 直連 DB 是否允許。切換任一環境需 Larry 明確批准。
---

# Environment Phase Matrix

| Environment | Phase | Claude 可連該 DB 執行 DDL | 連線方式 |
|-------------|-------|--------------------------|---------|
| `local-docker` | `dev` | ✅（走五步流程）| `docker exec agentic-rag-db psql ...` |
| `dev-vm` | *（已下線，待重建）* | - | GCP POC 資源 2026-08-19 全數清除（VM/DB/映像/bucket），Larry 表示線上 server 需重新建置 |
| `staging` | *（未建立）* | - | - |
| `production` | *（未建立）* | - | - |

**當前主要狀態**：
- `local-docker`：2026-08-20 以全新 volume 重建——`infra/schema.sql` bootstrap（41 表）+ 套用 `add_bot_config_versions.sql`、`backfill_bot_config_versions.sql`，`_applied_migrations` 有紀錄。**注意：無 seed 資料**（tenants/bots 空，需要時跑 `make seed-data`）。
- `dev-vm`：已不存在。重建後需以最新 `infra/schema.sql` bootstrap（它已含所有 migration 的最終形狀），並補 `_applied_migrations` 紀錄。

**切換記錄**：
- 2026-09-02 — `add_config_snapshots_and_audit_logs.sql`（Issue #60：config_snapshots / audit_logs 新表、traces 與 usage 的 config_hash）依 Larry 授權套用 local-docker、dev-vm、company-poc-vm 三環境，各自 `_applied_migrations` 已記錄（dev-vm / company 各 55 筆）。
- 2026-08-20（Phase C）— local-docker 套 `gcp_sync_prompt_optimizer.sql`（eval 三表，schema.sql 原本漏掉的 drift）+ `add_gate_settings.sql` + `add_eval_gate_flags.sql` + `add_prompt_gate_runs.sql`；schema.sql 修復為可乾淨 bootstrap（0 error / 46 表，暫存 DB 實測）。⚠️ 注意：DB 目前無 seed 資料，`add_gate_settings.sql` 的 system tenant UPDATE 為 0 列——**跑 `make seed-data` 之後需補跑該 UPDATE**（冪等，可直接重放整支 migration）。
- 2026-08-20 — dev-vm 標記為已下線（08-19 GCP 清空）；local-docker 全新重建 + Issue #54 Phase A migrations 套用。
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
