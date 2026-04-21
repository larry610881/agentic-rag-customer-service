-- S-Gov.6a — outcome snapshot + 3 複合 index
-- Plan: .claude/plans/agent-main-bright-leaf.md (S-Gov.6a)
--
-- agent_execution_traces 加 outcome 欄位（success / failed / partial）：
--   - 寫入時計算（_persist_trace 內 _compute_trace_outcome）
--   - 查詢時免解 nodes JSON
--   - 可加 index → outcome filter 高效
-- Backfill 用 ILIKE 粗略推算（accuracy 80-90% 可接受 — 新寫入會精確）

ALTER TABLE agent_execution_traces
    ADD COLUMN IF NOT EXISTS outcome VARCHAR(20);

UPDATE agent_execution_traces
SET outcome = (
    CASE
        WHEN nodes::text ILIKE '%"outcome": "failed"%' THEN 'failed'
        WHEN nodes::text ILIKE '%"outcome": "partial"%' THEN 'partial'
        ELSE 'success'
    END
)
WHERE outcome IS NULL;

CREATE INDEX IF NOT EXISTS ix_traces_tenant_conv_created
    ON agent_execution_traces(tenant_id, conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_traces_outcome_created
    ON agent_execution_traces(outcome, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_traces_bot_created
    ON agent_execution_traces(bot_id, created_at DESC);
