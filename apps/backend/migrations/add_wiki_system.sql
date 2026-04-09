-- Sprint W.1 — LLM Wiki Knowledge Mode
-- 新增 wiki_graphs 表（JSONB 儲存 Wiki Graph）+ bots.knowledge_mode 欄位
-- Plan: .claude/plans/luminous-launching-lobster.md
-- Issue: #26

-- ------------------------------------------------------------
-- 1. bots 表新增 knowledge_mode 欄位（預設 rag，backward compatible）
-- ------------------------------------------------------------
ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS knowledge_mode VARCHAR(20) NOT NULL DEFAULT 'rag';

-- ------------------------------------------------------------
-- 2. wiki_graphs 表 — Wiki BC 的聚合根 storage
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wiki_graphs (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    bot_id VARCHAR(36) NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    kb_id VARCHAR(36) NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | compiling | ready | stale | failed
    nodes JSONB NOT NULL DEFAULT '{}'::jsonb,
    edges JSONB NOT NULL DEFAULT '{}'::jsonb,
    backlinks JSONB NOT NULL DEFAULT '{}'::jsonb,
    clusters JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    compiled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 每個 bot 最多一個 wiki_graph（1:1）
CREATE UNIQUE INDEX IF NOT EXISTS ux_wiki_graphs_bot_id
    ON wiki_graphs(bot_id);

CREATE INDEX IF NOT EXISTS ix_wiki_graphs_tenant_id
    ON wiki_graphs(tenant_id);

CREATE INDEX IF NOT EXISTS ix_wiki_graphs_status
    ON wiki_graphs(status);

-- GIN index 供未來全文/結構查詢（Post-MVP Phase 2+ 會用到）
CREATE INDEX IF NOT EXISTS ix_wiki_graphs_nodes_gin
    ON wiki_graphs USING gin(nodes);
