-- Prompt optimization run history
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
