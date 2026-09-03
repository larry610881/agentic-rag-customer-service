-- Issue #68 P7a — agent_execution_traces.abuse_level：該回合主體的異常控管等級（0–4，NULL=未評估）
-- 冪等：IF NOT EXISTS

ALTER TABLE agent_execution_traces
    ADD COLUMN IF NOT EXISTS abuse_level INTEGER NULL;

-- 套用後記錄（每個環境各自執行）：
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_trace_abuse_level.sql', NOW(), 'claude-dev', 'dev');
