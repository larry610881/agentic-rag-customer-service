-- Issue #48 — 輸入端 LLM 防護獨立開關（角色切換 / prompt injection 語意偵測）
-- 與現有 llm_guard_enabled（輸出洩密防護）分開，因輸入防護每則訊息都跑、成本模型不同。
-- input_guard_prompt 欄位早已存在，本 migration 只補「是否啟用」的開關。

ALTER TABLE guard_rules_configs
    ADD COLUMN IF NOT EXISTS llm_input_guard_enabled BOOLEAN NOT NULL DEFAULT false;
