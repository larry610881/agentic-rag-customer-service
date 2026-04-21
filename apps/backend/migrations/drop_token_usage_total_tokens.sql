-- Token-Gov.6 — 刪除冗餘欄位 token_usage_records.total_tokens
-- 動機：與 input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens
--      重複儲存，違反 Single Source of Truth。
-- 相關 code 改動（必須先部署以下 code 再套此 migration，避免 runtime 500）：
--   - Domain UsageRecord.total_tokens 改為 @property（domain/usage/entity.py）
--   - Infrastructure 所有 SUM aggregate 改用 _TOTAL_TOKENS_EXPR
--     (= input + output + cache_read + cache_creation)
-- Issue: #36
-- Plan: .claude/plans/b-bug-delightful-starlight.md

ALTER TABLE token_usage_records
    DROP COLUMN IF EXISTS total_tokens;
