-- Issue #50 — per-worker 直接檢索模式（workflow 快速道）開關
-- Plan: GitHub Issue #50（六階段）
-- 預設 false：所有 worker 維持完整 ReAct，行為不變

ALTER TABLE bot_workers
    ADD COLUMN IF NOT EXISTS direct_retrieval BOOLEAN NOT NULL DEFAULT false;
