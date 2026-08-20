-- Issue #54 Phase C — Gate run 狀態表（含逐題報告 details）
-- Plan: .claude/plans/prompt-gate-phase-c-plan.md §2 M3；spec §3.4/§4.5
-- Issue: #54

CREATE TABLE IF NOT EXISTS prompt_gate_runs (
    id                VARCHAR(36) PRIMARY KEY,
    tenant_id         VARCHAR(36) NOT NULL,
    bot_id            VARCHAR(36) NOT NULL,
    version_id        VARCHAR(36) NOT NULL
        REFERENCES bot_config_versions(id) ON DELETE CASCADE,
    status            VARCHAR(20) NOT NULL DEFAULT 'queued',
        -- queued | running | completed | error
    verdict           VARCHAR(10),
        -- pass | fail（completed 才有）
    fail_reasons      JSONB,
        -- ["hard_gate","soft_gate","budget_exceeded"] 可複合
    dataset_ids       JSONB NOT NULL DEFAULT '[]'::jsonb,
    repeats           INTEGER NOT NULL DEFAULT 3,
    soft_threshold    DOUBLE PRECISION NOT NULL DEFAULT 0.8,
    total_cases       INTEGER,
    hard_failed_cases INTEGER,
    soft_pass_rate    DOUBLE PRECISION,
    unstable_cases    INTEGER,
    est_cost          DOUBLE PRECISION,
    actual_cost       DOUBLE PRECISION,
    input_tokens      BIGINT,
    output_tokens     BIGINT,
    details           JSONB,
        -- 逐題報告（spec §4.5）：response 4KB 截斷 + 斷言明細 + compact trace nodes
    error_message     TEXT,
    triggered_by      TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_pgr_bot_created
    ON prompt_gate_runs (bot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_pgr_tenant
    ON prompt_gate_runs (tenant_id);
