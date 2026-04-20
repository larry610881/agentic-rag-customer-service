-- S-Token-Gov.2 — Token Ledger（月度帳本） + Tenant.included_categories
-- Plan: .claude/plans/agent-main-bright-leaf.md
-- 用於：扣費記帳 (base_remaining + addon_remaining) + 月度重置 cron
--       per-tenant 勾選哪些 category 計入額度

CREATE TABLE IF NOT EXISTS token_ledgers (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_year_month VARCHAR(7) NOT NULL,           -- "YYYY-MM" 格式
    plan_name VARCHAR(50) NOT NULL,                 -- snapshot：plan 改名 history 不變
    base_total BIGINT NOT NULL DEFAULT 0,           -- 該月初始額度（snapshot from plan）
    base_remaining BIGINT NOT NULL DEFAULT 0,
    addon_remaining BIGINT NOT NULL DEFAULT 0,      -- 上月 carryover + 本月 auto-topup（Token-Gov.3）
    total_used_in_cycle BIGINT NOT NULL DEFAULT 0,  -- 累計用量（即使超額也記）
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ledger_tenant_cycle UNIQUE (tenant_id, cycle_year_month)
);

CREATE INDEX IF NOT EXISTS ix_token_ledgers_tenant_cycle
    ON token_ledgers(tenant_id, cycle_year_month);

-- Tenant 加 included_categories
-- 規則：NULL = 全部 category 計入；list = 只計入列表內的；[] = 全部不計入
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS included_categories JSONB;

COMMENT ON COLUMN tenants.included_categories IS
    'NULL = 全部 category 計入額度；list = 只計入列表內的；[] = 全部不計入';
