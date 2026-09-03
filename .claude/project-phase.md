---
name: Project Deployment Phase（多環境）
description: 每個部署環境獨立的階段旗標。Claude 依此判斷對該環境執行 migration / DDL / 直連 DB 是否允許。切換任一環境需 Larry 明確批准。
---

# Environment Phase Matrix

| Environment | Phase | Claude 可連該 DB 執行 DDL | 連線方式 |
|-------------|-------|--------------------------|---------|
| `local-docker` | `dev` | ✅（走五步流程）| `docker exec agentic-rag-db psql ...` |
| `dev-vm` | `dev` | ✅（每次需 Larry 授權 + 走五步流程）| IAP SSH 進 `db-services` → `sudo docker exec -i postgres psql -U postgres -d agentic_rag` |
| `company-poc-vm` | `dev` | ✅（每次需 Larry 授權 + 走五步流程）| 公司帳號 `larry610881@gcpmail.pcsc.net.tw`，IAP SSH 進 `poc-rag-vm-01`（project-pic-ai-innovation-poc）→ `sudo docker exec -i postgres psql -U postgres -d agentic_rag` |
| `staging` | *（未建立）* | - | - |
| `production` | *（未建立）* | - | - |

**當前主要狀態**：
- **2026-09-03（#67）**：`add_api_keys.sql`、`add_users_token_version.sql` 已套 `local-docker` 與 `company-poc-vm`（各驗證 + `_applied_migrations` 紀錄，applied_by=claude-dev）。
- `company-poc-vm`：**2026-08-31 首次建置**（公司 GCP `project-pic-ai-innovation-poc`，VM `poc-rag-vm-01` e2-standard-4，五容器 bind mount `/data/*`，內網 10.0.0.2）。`infra/schema.sql` bootstrap（46 表）+ 54 筆 migration 紀錄（`schema.sql-bootstrap-2026-08-31`）+ 最小 seed（2 tenants + admin@system.com + gate=TRUE）。Cloud Run `agentic-rag` rev 00004（映像 `7bf93f6-admin1`，含 admin SPA）health 200、Require auth 中。密鑰暫以 env var 注入，`rag-*` Secret Manager 已寫入待 run-SA 授權後切換。
- `dev-vm`：**2026-08-24 全新重建完成**（VM `db-services` e2-standard-2 / Ubuntu 24.04 / internal 10.140.0.3，五容器 postgres+redis+etcd+minio+milvus，全新強密碼——舊 repo 內外洩密碼已棄用）。`infra/schema.sql` bootstrap（46 表含 `_applied_migrations`）+ 54 筆 migration 紀錄（53 檔 + `schema.sql-bootstrap-2026-08-24`）。最小 seed：2 tenants + admin@system.com + system tenant `prompt_gate_enabled=TRUE`。**未 seed**：provider_settings / bots / KB（舊匯出用舊 ENCRYPTION_MASTER_KEY 加密 + 舊 schema shape，由 Larry 從 UI 重建）。Cloud Run `agentic-rag` rev 00001（main @ PR #55 merge）+ arq-worker 已跑。
- `local-docker`：2026-08-20 以全新 volume 重建——`infra/schema.sql` bootstrap（41 表）+ 套用 `add_bot_config_versions.sql`、`backfill_bot_config_versions.sql`，`_applied_migrations` 有紀錄。**注意：無 seed 資料**（tenants/bots 空，需要時跑 `make seed-data`）。
- `dev-vm`：已不存在。重建後需以最新 `infra/schema.sql` bootstrap（它已含所有 migration 的最終形狀），並補 `_applied_migrations` 紀錄。

**切換記錄**：
- 2026-09-03 — Larry 宣告 **dev-vm 退役**（project-4dc6cadb `db-services` 不再是 migration 目標）；dev 階段環境只剩 `local-docker` 與 `company-poc-vm`。同日 `add_bot_mode.sql`（Issue #66：bots.mode fast|deep）依授權套用兩環境並寫入 `_applied_migrations`（local 11 筆、company 56 筆）。
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
