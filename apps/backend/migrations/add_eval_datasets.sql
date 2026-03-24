-- Eval datasets for prompt optimization
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
