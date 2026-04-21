-- S-Gov.6b: 對話 LLM 摘要 + Race-safe 觸發追蹤
-- Plan: .claude/plans/agent-main-bright-leaf.md (S-Gov.6b)
--
-- conversations 加 5 欄位支援 LLM 摘要 cron 觸發 + race-safe 重生：
--   summary                   TEXT — LLM 生的中文一句話摘要
--   message_count             INT — 寫 message 時 +1（race-safe snapshot 對照）
--   summary_message_count     INT — LLM 完成時 snapshot 的 message_count
--   last_message_at           TIMESTAMPTZ — 寫 message 時更新（cron 判斷閒置）
--   summary_at                TIMESTAMPTZ — LLM 完成時間
--
-- Cron 觸發條件（5 分鐘閒置 + 對話有變化）：
--   WHERE last_message_at < NOW() - INTERVAL '5 minutes'
--     AND (summary IS NULL OR summary_message_count < message_count)
-- → 自動處理「summary 生成中對話又動」case，不需 lock 不需 cancel job

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS message_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS summary_message_count INTEGER,
    ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS summary_at TIMESTAMPTZ;

-- Backfill 既有 conversations（從 messages SUM/MAX 拉）
UPDATE conversations c
SET message_count = sub.cnt,
    last_message_at = sub.last_at
FROM (
    SELECT conversation_id, COUNT(*) AS cnt, MAX(created_at) AS last_at
    FROM messages
    GROUP BY conversation_id
) sub
WHERE c.id = sub.conversation_id;

-- Partial index — 只 index pending summary 的 row
-- cron 每分鐘掃這個 partial set，避免全表掃描
CREATE INDEX IF NOT EXISTS ix_conversations_pending_summary
    ON conversations(last_message_at)
    WHERE summary IS NULL OR summary_message_count < message_count;
