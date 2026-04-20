-- S-Token-Gov.1 — Plan Template 表
-- Plan: .claude/plans/agent-main-bright-leaf.md
-- 用於：方案模板管理 + 租戶綁 plan，後續 Token-Gov.2 ledger 會從此表讀取
--       base_monthly_tokens / addon_pack_tokens 作為扣費 / 自動續約依據

CREATE TABLE IF NOT EXISTS plans (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    base_monthly_tokens BIGINT NOT NULL DEFAULT 0,
    addon_pack_tokens BIGINT NOT NULL DEFAULT 0,
    base_price NUMERIC(10, 2) NOT NULL DEFAULT 0,
    addon_price NUMERIC(10, 2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'TWD',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_plans_active ON plans(is_active);

-- Seed 3 個預設 plan（POC / Starter / Pro），冪等
INSERT INTO plans (id, name, base_monthly_tokens, addon_pack_tokens, base_price, addon_price, currency, description)
VALUES
    (gen_random_uuid()::text, 'poc', 10000000, 5000000, 0, 0, 'TWD', '內部 POC 測試 — 免計費'),
    (gen_random_uuid()::text, 'starter', 10000000, 5000000, 3000, 1500, 'TWD', '基礎方案 — 月 1000 萬 token / 加值包 500 萬'),
    (gen_random_uuid()::text, 'pro', 30000000, 15000000, 8000, 3500, 'TWD', '專業方案 — 月 3000 萬 token / 加值包 1500 萬')
ON CONFLICT (name) DO NOTHING;
