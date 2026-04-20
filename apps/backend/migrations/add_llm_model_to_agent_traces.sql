-- Observability — Trace 層記錄 LLM 模型，支援 A/B 測試可觀測性
-- Agent Execution Trace 新增三欄：llm_model、llm_provider、bot_id

ALTER TABLE agent_execution_traces
    ADD COLUMN IF NOT EXISTS llm_model    VARCHAR(100) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(50)  NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS bot_id       VARCHAR(36)           DEFAULT NULL;

CREATE INDEX IF NOT EXISTS ix_agent_exec_traces_bot_id
    ON agent_execution_traces (bot_id);
