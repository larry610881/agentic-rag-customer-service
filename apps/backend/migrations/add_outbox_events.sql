-- Outbox Pattern Phase A — outbox_events 表
-- Plan: ~/.claude/plans/snuggly-jingling-aho.md（附錄 + Phase A-F 整合 plan）
--
-- 動機：DB ↔ Milvus 雙寫沒有原子性。先把 DELETE 類事件 outbox 化，
-- 在 PG transaction 內 INSERT outbox row + 業務 SQL → commit → async
-- worker drain 對 Milvus 套用 → eventual consistency + crash safe。
--
-- Phase A 建表 + 紀錄；Phase B-D 才有業務 use case 寫入（drain 此期間
-- 永遠空轉，無副作用）。範圍只 DELETE，UPSERT 不納入（理由與觸發
-- 升級閾值見 memory/outbox-upsert-trigger-thresholds.md）。

CREATE TABLE IF NOT EXISTS outbox_events (
    id                 VARCHAR(36) PRIMARY KEY,            -- uuid4 = idempotency key
    tenant_id          VARCHAR(36) NOT NULL,
    aggregate_type     VARCHAR(40) NOT NULL,                -- knowledge_base | document | document_source | chunk
    aggregate_id       VARCHAR(64) NOT NULL,
    event_type         VARCHAR(40) NOT NULL,                -- vector.delete | vector.drop_collection
    payload            JSONB NOT NULL,                      -- collection / filters / doc_ids
    doc_watermark_ts   TIMESTAMPTZ NULL,                    -- doc-id reuse guard（Phase C 用）
    status             VARCHAR(16) NOT NULL DEFAULT 'pending', -- pending | in_progress | done | dead
    attempts           INT NOT NULL DEFAULT 0,
    max_attempts       INT NOT NULL DEFAULT 8,
    next_attempt_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error         TEXT NULL,
    locked_by          VARCHAR(64) NULL,                    -- lease holder worker id
    locked_at          TIMESTAMPTZ NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ NULL,
    CONSTRAINT chk_outbox_status CHECK (status IN ('pending','in_progress','done','dead'))
);

-- drain worker 撈 batch 用 — partial index 只覆蓋活躍狀態，比 full index 小很多
CREATE INDEX IF NOT EXISTS ix_outbox_drain
    ON outbox_events (status, next_attempt_at)
    WHERE status IN ('pending','in_progress');

-- DLQ 列表用
CREATE INDEX IF NOT EXISTS ix_outbox_dlq
    ON outbox_events (status, created_at DESC)
    WHERE status = 'dead';

-- 依 aggregate 查歷史用（debug / audit）
CREATE INDEX IF NOT EXISTS ix_outbox_aggregate
    ON outbox_events (aggregate_type, aggregate_id);

-- ── 紀錄 migration ────────────────────────────────────────────────
-- Phase A：建 outbox 基礎建設，無業務 use case 寫入
-- INSERT INTO _applied_migrations (filename, applied_at, applied_by, phase)
-- VALUES ('add_outbox_events.sql', NOW(), 'claude-dev', 'dev');
-- ↑ 取消註解後手動 apply（migration-workflow.md 五步流程 Step 5）
