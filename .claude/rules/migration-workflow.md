# Migration 工作流程規範（編輯 apps/backend/migrations/*.sql 或 apps/backend/src/infrastructure/db/models/*.py 時自動套用）

## 核心原則

> **DDL 不是程式碼，是對資料的手術。先看 SQL、親手執行、立即驗證、留下紀錄。**

本專案**無 Alembic / 無 auto-migration**，所有 schema 變更都必須有對應的 `.sql` 檔案 + 人工確認路徑。

## Phase Gate（先看階段再決定怎麼做）

執行任何 DDL 前，**必須先讀 `.claude/project-phase.md`** 確認當前 `phase`：

| Phase | Claude 可執行的動作 |
|-------|---------------------|
| `poc-dev` | ✅ 可連 dev DB（本地 Docker 或 GCP VM）執行 DDL，必須走完下方「POC 五步流程」 |
| `pre-prod` / `production` | ❌ **禁止**任何直連 DB 執行 DDL 的指令。只能產出 `.sql` 檔 + 更新 `infra/schema.sql`，套用動作由 Larry / DBA / CI pipeline 負責 |

違反 Phase Gate = CRITICAL 違規。Claude 必須拒絕執行，並回覆「當前 phase 為 X，需由 人工/pipeline 套用」。

## POC-dev 階段：五步流程（缺一不可）

### Step 1 — 寫 SQL 檔

路徑：`apps/backend/migrations/<description>.sql`

```sql
-- <SPRINT/Bug 來源> — <一句話說明>
-- Plan: .claude/plans/<plan-file>.md （如有）
-- Issue: #<N> （如有）

ALTER TABLE <table>
    ADD COLUMN IF NOT EXISTS <column> <type> DEFAULT <value>;
```

- 優先用 `IF NOT EXISTS` / `IF EXISTS` 保持冪等
- 多個邏輯相關的欄位可放同一個檔，**不相關的拆檔**

### Step 2 — Preview：顯示 SQL 讓 Larry 確認

執行前必須貼完整 SQL 在對話中，並明確詢問：

> 即將對 <DB 位置> 執行以上 SQL，是否確認？

**除非 Larry 回覆明確肯定（「確認」「做」「go」等），否則不得執行**。

### Step 3 — 執行

依照連線環境選一種（參考 memory `gcp-db-connection.md`）：

```bash
# 本地 Docker PostgreSQL
docker exec agentic-rag-db psql -U postgres -d agentic_rag -c "<SQL>"

# GCP VM (IAP tunnel)
/home/p10359945/google-cloud-sdk/bin/gcloud compute ssh db-services \
  --zone=asia-east1-b --tunnel-through-iap \
  --project=project-4dc6cadb-5d47-4482-a32 \
  --command='docker exec agentic-rag-db psql -U postgres -d agentic_rag -c "<SQL>"'
```

- ❌ **禁止**用 Python script + SQLAlchemy engine 執行 DDL（除非 Larry 明確要求）。直接 psql 更符合 DBA 流程，能看到完整 output。

### Step 4 — Verify：執行後立即驗證

```sql
-- 確認欄位存在
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name='<table>' AND column_name='<column>';
```

或 `\d <table>`（psql meta-command）。驗證未通過 → 視為未執行，重新檢查 SQL / 連線。

### Step 5 — 紀錄 + 同步 schema.sql

```sql
-- 紀錄 migration 已套用
INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
VALUES ('<filename>.sql', NOW(), 'claude-poc', 'poc-dev');
```

並同步更新 `infra/schema.sql`（source of truth）——把新增的欄位加進對應 `CREATE TABLE` 區塊。

## `_applied_migrations` 表

若此表不存在，第一次執行 migration 前先建：

```sql
CREATE TABLE IF NOT EXISTS _applied_migrations (
    filename VARCHAR(200) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by VARCHAR(100) NOT NULL,  -- 'claude-poc' | 'larry-manual' | 'ci-pipeline'
    phase VARCHAR(20) NOT NULL         -- 'poc-dev' | 'pre-prod' | 'production'
);
```

此表是追蹤「哪支 DB 套過哪個 migration」的唯一依據，未來切到 pre-prod / prod 也沿用，CI pipeline 寫入時填 `applied_by='ci-pipeline'`。

## ORM Model 與 Migration 的關係

修改 `apps/backend/src/infrastructure/db/models/*.py`（新增欄位）時：

1. 一併寫 `migrations/*.sql`
2. 更新 `infra/schema.sql`
3. 完整走上面五步流程

**禁止**只改 ORM 不寫 migration — 下次部署會 runtime 炸裂（`column does not exist`）。

## 違規掃描（Code Review / Stop hook）

| 違規 | 級別 |
|------|------|
| ORM model 新增欄位但無對應 `migrations/*.sql` | CRITICAL |
| `migrations/*.sql` 存在但 `_applied_migrations` 無紀錄 | CRITICAL（POC 階段）|
| `infra/schema.sql` 未同步 | HIGH |
| Phase 為 `pre-prod`/`production` 時 Claude 執行了 DDL | CRITICAL |
| 用 Python script + engine 跑 DDL（繞過 psql preview）| MEDIUM |

## 例外情境

| 情境 | 處理方式 |
|------|---------|
| `DROP TABLE` / `DROP COLUMN` | 即使 POC 也要 Larry **口頭明確確認**（不可依賴 Claude 的 preview 自動判斷） |
| Data migration（`UPDATE ... SET ...`）| 同 DDL 走五步流程，Step 2 preview 要附「預期影響的 row 數」|
| 批次 migration（多檔） | 每個檔都走完整五步，**不合併**，避免一支失敗難回滾 |
