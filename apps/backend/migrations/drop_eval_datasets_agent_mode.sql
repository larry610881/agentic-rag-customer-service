-- #469965 — 移除殘留欄位 eval_datasets.agent_mode
-- ORM 已於 ce97472 / 558be1f 移除；線上仍在（varchar(20) NOT NULL DEFAULT 'router'），
-- 無任何程式讀寫（prompt_optimizer/db_client.py 的 raw SQL 已於同一分支移除）。
-- DROP 經 Larry 口頭同意；每個環境逐一 preview + 授權後執行。

ALTER TABLE eval_datasets
    DROP COLUMN IF EXISTS agent_mode;
