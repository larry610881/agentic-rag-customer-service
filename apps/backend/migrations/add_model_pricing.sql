-- S-Pricing.1 — Pricing admin UI + 回溯重算
-- Plan: .claude/plans/b-bug-delightful-starlight.md
-- Issue: #38
-- 用於：把 hardcoded DEFAULT_MODELS 搬進 DB，append-only 版本結構
--       舊版本的 effective_to 在新版本建立時被釘死，保 token_usage_records
--       的 estimated_cost snapshot 不被事後修改
--       回溯重算透過獨立 dry-run + execute 兩段式流程，每次留 audit 紀錄

CREATE TABLE IF NOT EXISTS model_pricing (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider             VARCHAR(50) NOT NULL,
    model_id             VARCHAR(200) NOT NULL,
    display_name         VARCHAR(200) NOT NULL,
    category             VARCHAR(20) NOT NULL DEFAULT 'llm',
    input_price          NUMERIC(12,6) NOT NULL,
    output_price         NUMERIC(12,6) NOT NULL,
    cache_read_price     NUMERIC(12,6) NOT NULL DEFAULT 0,
    cache_creation_price NUMERIC(12,6) NOT NULL DEFAULT 0,
    effective_from       TIMESTAMPTZ NOT NULL,
    effective_to         TIMESTAMPTZ NULL,
    created_by           VARCHAR(100) NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note                 TEXT NULL,
    CONSTRAINT chk_prices_non_negative CHECK (
        input_price >= 0 AND output_price >= 0
        AND cache_read_price >= 0 AND cache_creation_price >= 0
    ),
    CONSTRAINT chk_effective_range CHECK (
        effective_to IS NULL OR effective_to > effective_from
    )
);

CREATE INDEX IF NOT EXISTS idx_model_pricing_lookup
    ON model_pricing(provider, model_id, effective_from DESC);

CREATE INDEX IF NOT EXISTS idx_model_pricing_effective
    ON model_pricing(effective_from DESC);

CREATE TABLE IF NOT EXISTS pricing_recalc_audit (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pricing_id         UUID NOT NULL REFERENCES model_pricing(id),
    recalc_from        TIMESTAMPTZ NOT NULL,
    recalc_to          TIMESTAMPTZ NOT NULL,
    affected_rows      INTEGER NOT NULL,
    cost_before_total  NUMERIC(15,6) NOT NULL,
    cost_after_total   NUMERIC(15,6) NOT NULL,
    executed_by        VARCHAR(100) NOT NULL,
    executed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason             TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pricing_recalc_audit_executed
    ON pricing_recalc_audit(executed_at DESC);

ALTER TABLE token_usage_records
    ADD COLUMN IF NOT EXISTS cost_recalc_at TIMESTAMPTZ NULL;
