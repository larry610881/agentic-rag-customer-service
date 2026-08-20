-- Issue #54 Phase A — Backfill：每個既有 bot 以現行設定建 version 1
-- Plan: docs/prompt-gate-spec.md §3.5
-- Issue: #54
-- 冪等：已有版本列的 bot 不重建。快照白名單對齊
-- src/domain/prompt_gate/config_snapshot.py（mcp_bindings 剝除 env_values）。

INSERT INTO bot_config_versions (
    id, tenant_id, bot_id, version_no, config_snapshot, snapshot_schema,
    changed_fields, status, is_current, source, gate_verdict,
    published_at, created_at
)
SELECT
    gen_random_uuid()::text,
    b.tenant_id,
    b.id,
    1,
    jsonb_build_object(
        'base_prompt', b.base_prompt,
        'bot_prompt', b.bot_prompt,
        'memory_extraction_prompt', b.memory_extraction_prompt,
        'query_rewrite_extra_hint', b.query_rewrite_extra_hint,
        'hyde_extra_hint', b.hyde_extra_hint,
        'llm_provider', b.llm_provider,
        'llm_model', b.llm_model,
        'router_model', b.router_model,
        'summary_model', b.summary_model,
        'rag_retrieval_modes', to_jsonb(b.rag_retrieval_modes),
        'query_rewrite_enabled', b.query_rewrite_enabled,
        'query_rewrite_model', b.query_rewrite_model,
        'hyde_enabled', b.hyde_enabled,
        'hyde_model', b.hyde_model,
        'rerank_enabled', b.rerank_enabled,
        'rerank_model', b.rerank_model,
        'rerank_top_n', b.rerank_top_n,
        'enabled_tools', to_jsonb(b.enabled_tools),
        'max_tool_calls', b.max_tool_calls,
        'memory_enabled', b.memory_enabled,
        'memory_extraction_threshold', b.memory_extraction_threshold,
        'knowledge_base_ids', COALESCE(
            (SELECT jsonb_agg(bkb.knowledge_base_id ORDER BY bkb.knowledge_base_id)
             FROM bot_knowledge_bases bkb WHERE bkb.bot_id = b.id),
            '[]'::jsonb
        ),
        'llm_params', jsonb_build_object(
            'temperature', b.temperature,
            'max_tokens', b.max_tokens,
            'history_limit', b.history_limit,
            'frequency_penalty', b.frequency_penalty,
            'reasoning_effort', b.reasoning_effort,
            'rag_top_k', b.rag_top_k,
            'rag_score_threshold', b.rag_score_threshold
        ),
        'tool_configs', COALESCE(to_jsonb(b.tool_configs), '{}'::jsonb),
        -- 紅線：env_values 剝除，只存 registry_id + enabled_tools
        'mcp_bindings', COALESCE(
            (SELECT jsonb_agg(jsonb_build_object(
                 'registry_id', mb->'registry_id',
                 'enabled_tools', COALESCE(mb->'enabled_tools', '[]'::jsonb)
             ))
             FROM jsonb_array_elements(to_jsonb(b.mcp_bindings)) AS mb),
            '[]'::jsonb
        )
    ),
    1,
    '[]'::jsonb,
    'published',
    TRUE,
    'seed',
    'skipped',
    NOW(),
    NOW()
FROM bots b
WHERE NOT EXISTS (
    SELECT 1 FROM bot_config_versions v WHERE v.bot_id = b.id
);
