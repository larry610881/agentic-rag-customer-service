-- BUG-01 — Persist tool-generated rich content payload (contact / sources / blocks)
-- Web Bot 重新載入歷史對話時還原 rich content。LINE 不受影響（payload 已送達手機端）。
-- Plan: .claude/plans/harmonic-booping-sparkle.md
-- Issue: #29

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS structured_content TEXT DEFAULT NULL;
