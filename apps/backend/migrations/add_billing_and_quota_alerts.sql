-- S-Token-Gov.3 — 自動續約交易紀錄 + 額度警示 log
-- Plan: .claude/plans/agent-main-bright-leaf.md (Token-Gov.3)
--
-- billing_transactions: append-only ledger of billing events
--   - auto-topup 觸發時寫入一筆，含金額 + reason
--   - snapshot plan_name / amount_currency / amount_value（plan 後改價歷史不變）
-- quota_alert_logs: 警示通知 log
--   - cron 每天跑，達 80% / 100% 寫入
--   - UNIQUE(tenant_id, cycle, alert_type) 保證 DB 層冪等

CREATE TABLE IF NOT EXISTS billing_transactions (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ledger_id VARCHAR(36) NOT NULL REFERENCES token_ledgers(id) ON DELETE CASCADE,
    cycle_year_month VARCHAR(7) NOT NULL,
    plan_name VARCHAR(50) NOT NULL,
    transaction_type VARCHAR(30) NOT NULL,
    addon_tokens_added BIGINT NOT NULL,
    amount_currency VARCHAR(10) NOT NULL,
    amount_value NUMERIC(12,2) NOT NULL,
    triggered_by VARCHAR(20) NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_billing_transactions_tenant_cycle
    ON billing_transactions(tenant_id, cycle_year_month);
CREATE INDEX IF NOT EXISTS ix_billing_transactions_created
    ON billing_transactions(created_at DESC);

CREATE TABLE IF NOT EXISTS quota_alert_logs (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_year_month VARCHAR(7) NOT NULL,
    alert_type VARCHAR(30) NOT NULL,
    used_ratio NUMERIC(5,4) NOT NULL,
    message TEXT,
    delivered_to_email BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_quota_alert_unique UNIQUE (tenant_id, cycle_year_month, alert_type)
);
CREATE INDEX IF NOT EXISTS ix_quota_alert_logs_created
    ON quota_alert_logs(created_at DESC);
