-- S-Ledger-Unification P1 — append-only topups 表
-- Issue: #41
-- 目的：取代 token_ledgers.addon_remaining mutable 欄位
-- 設計：一個 (tenant_id, cycle_year_month) 可以有多筆 topup（auto/manual/carryover）
--       addon_remaining = SUM(amount) - overage（overage 從 usage_records 算）
--       計算在 ComputeTenantQuotaUseCase 裡統一做，table 本身只負責記帳

CREATE TABLE IF NOT EXISTS token_ledger_topups (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_year_month VARCHAR(7) NOT NULL,           -- "YYYY-MM"
    amount BIGINT NOT NULL,                          -- 正=加值，負=退款/手動扣
    reason VARCHAR(32) NOT NULL,                     -- auto_topup | manual_adjust | carryover
    pricing_version VARCHAR(32),                     -- optional snapshot (auto_topup 有)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_token_ledger_topups_tenant_cycle
    ON token_ledger_topups(tenant_id, cycle_year_month);

COMMENT ON TABLE token_ledger_topups IS
    'Append-only log of addon topups per tenant+cycle. 取代 token_ledgers.addon_remaining mutable 欄位。';
