-- ============================================================
-- GCP VM DB Migration Script — Prompt Optimizer
-- 執行方式: psql -h <GCP_HOST> -U <USER> -d agentic_rag -f gcp_sync_prompt_optimizer.sql
-- ============================================================

-- 1. bots 表新增欄位（如已存在會跳過）
ALTER TABLE bots ADD COLUMN IF NOT EXISTS busy_reply_message VARCHAR(500) NOT NULL DEFAULT '小編正在努力回覆中，請稍等一下喔～';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS line_show_sources BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Prompt Optimization Run History
CREATE TABLE IF NOT EXISTS prompt_opt_runs (
    id VARCHAR(36) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    iteration INTEGER NOT NULL,
    tenant_id VARCHAR(36) NOT NULL,
    target_field VARCHAR(50) NOT NULL,
    bot_id VARCHAR(36),
    prompt_snapshot TEXT NOT NULL,
    score FLOAT NOT NULL,
    passed_count INTEGER NOT NULL,
    total_count INTEGER NOT NULL,
    is_best BOOLEAN DEFAULT FALSE,
    details JSON,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_prompt_opt_runs_run_id ON prompt_opt_runs(run_id);
CREATE INDEX IF NOT EXISTS ix_prompt_opt_runs_bot_id ON prompt_opt_runs(bot_id);
CREATE INDEX IF NOT EXISTS ix_prompt_opt_runs_created_at ON prompt_opt_runs(created_at);

-- 3. Eval Datasets（UI 管理用）
CREATE TABLE IF NOT EXISTS eval_datasets (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    bot_id VARCHAR(36),
    name VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    target_prompt VARCHAR(50) NOT NULL DEFAULT 'base_prompt',
    agent_mode VARCHAR(20) NOT NULL DEFAULT 'router',
    default_assertions JSON,
    cost_config JSON,
    include_security BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_eval_datasets_tenant_id ON eval_datasets(tenant_id);

-- 4. Eval Test Cases
CREATE TABLE IF NOT EXISTS eval_test_cases (
    id VARCHAR(36) PRIMARY KEY,
    dataset_id VARCHAR(36) NOT NULL REFERENCES eval_datasets(id) ON DELETE CASCADE,
    case_id VARCHAR(100) NOT NULL,
    question TEXT NOT NULL,
    priority VARCHAR(5) NOT NULL DEFAULT 'P1',
    category VARCHAR(100) DEFAULT '',
    conversation_history JSON,
    assertions JSON NOT NULL,
    tags JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_eval_test_cases_dataset_id ON eval_test_cases(dataset_id);

-- ============================================================
-- 驗證
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '=== Migration Complete ===';
    RAISE NOTICE 'bots.busy_reply_message: %', (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='bots' AND column_name='busy_reply_message');
    RAISE NOTICE 'bots.line_show_sources: %', (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='bots' AND column_name='line_show_sources');
    RAISE NOTICE 'prompt_opt_runs: %', (SELECT COUNT(*) FROM information_schema.tables WHERE table_name='prompt_opt_runs');
    RAISE NOTICE 'eval_datasets: %', (SELECT COUNT(*) FROM information_schema.tables WHERE table_name='eval_datasets');
    RAISE NOTICE 'eval_test_cases: %', (SELECT COUNT(*) FROM information_schema.tables WHERE table_name='eval_test_cases');
END $$;
