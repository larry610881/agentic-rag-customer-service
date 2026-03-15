-- Memory Bounded Context: visitor profiles, identities, and memory facts
-- Also adds memory configuration columns to bots table

-- 1. Visitor profiles (aggregate root)
CREATE TABLE IF NOT EXISTS visitor_profiles (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    display_name VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_visitor_profiles_tenant ON visitor_profiles(tenant_id);

-- 2. Visitor identities (maps external IDs to profiles)
CREATE TABLE IF NOT EXISTS visitor_identities (
    id VARCHAR(36) PRIMARY KEY,
    profile_id VARCHAR(36) NOT NULL REFERENCES visitor_profiles(id) ON DELETE CASCADE,
    tenant_id VARCHAR(36) NOT NULL,
    source VARCHAR(20) NOT NULL,
    external_id VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_identity_lookup UNIQUE (tenant_id, source, external_id)
);
CREATE INDEX IF NOT EXISTS ix_visitor_identities_profile ON visitor_identities(profile_id);

-- 3. Memory facts (long-term memory storage)
CREATE TABLE IF NOT EXISTS memory_facts (
    id VARCHAR(36) PRIMARY KEY,
    profile_id VARCHAR(36) NOT NULL REFERENCES visitor_profiles(id) ON DELETE CASCADE,
    tenant_id VARCHAR(36) NOT NULL,
    memory_type VARCHAR(20) NOT NULL DEFAULT 'long_term',
    category VARCHAR(30) NOT NULL DEFAULT 'custom',
    key VARCHAR(200) NOT NULL,
    value TEXT NOT NULL,
    source_conversation_id VARCHAR(36),
    confidence FLOAT NOT NULL DEFAULT 1.0,
    last_accessed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_memory_fact_key UNIQUE (profile_id, key)
);
CREATE INDEX IF NOT EXISTS ix_memory_facts_profile ON memory_facts(profile_id);
CREATE INDEX IF NOT EXISTS ix_memory_facts_tenant ON memory_facts(tenant_id);
CREATE INDEX IF NOT EXISTS ix_memory_facts_profile_type ON memory_facts(profile_id, memory_type);

-- 4. Bot memory configuration columns
ALTER TABLE bots ADD COLUMN IF NOT EXISTS memory_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS memory_extraction_threshold INTEGER NOT NULL DEFAULT 3;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS memory_extraction_prompt TEXT NOT NULL DEFAULT '';
