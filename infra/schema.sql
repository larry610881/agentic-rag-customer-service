--
-- PostgreSQL database dump
--

\restrict QKlvJhIklbFIPUA8XbC0Nf7vIaW9SnqahESmB3a8cHI4r9OSGb5U96iCzOoRZMA

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _applied_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public._applied_migrations (
    filename character varying(200) NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    applied_by character varying(100) NOT NULL,
    phase character varying(20) NOT NULL
);


--
-- Name: agent_execution_traces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.config_snapshots (
    hash character varying(64) NOT NULL,
    snapshot json NOT NULL,
    snapshot_schema integer DEFAULT 1 NOT NULL,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL
);


CREATE TABLE public.api_keys (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    name character varying(100) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    secret_hash character varying(64) NOT NULL,
    secret_salt character varying(32) NOT NULL,
    secret_prefix character varying(16) NOT NULL,
    scopes json DEFAULT '[]'::json NOT NULL,
    allowed_bot_ids json DEFAULT '[]'::json NOT NULL,
    expires_at timestamp with time zone,
    revoked_at timestamp with time zone,
    token_version integer DEFAULT 1 NOT NULL,
    last_used_at timestamp with time zone,
    created_by character varying(36),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


CREATE TABLE public.audit_logs (
    id character varying(36) NOT NULL,
    tenant_id character varying(36),
    actor_user_id character varying(36),
    entity_type character varying(40) NOT NULL,
    entity_id character varying(100) NOT NULL,
    action character varying(20) NOT NULL,
    changed_fields json,
    source character varying(20) DEFAULT 'api'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


CREATE TABLE public.abuse_settings (
    id character varying(36) NOT NULL,
    scope_kind character varying(20) NOT NULL,
    scope_id character varying(64) NOT NULL,
    overrides json DEFAULT '{}'::json NOT NULL,
    updated_by character varying(36),
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


CREATE TABLE public.agent_execution_traces (
    id character varying(36) NOT NULL,
    trace_id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    message_id character varying(36),
    conversation_id character varying(36),
    agent_mode character varying(30) NOT NULL,
    nodes json,
    total_ms double precision NOT NULL,
    total_tokens json,
    created_at timestamp with time zone NOT NULL,
    source character varying(20) DEFAULT ''::character varying NOT NULL,
    llm_model character varying(100) DEFAULT ''::character varying NOT NULL,
    llm_provider character varying(50) DEFAULT ''::character varying NOT NULL,
    bot_id character varying(36) DEFAULT NULL::character varying,
    outcome character varying(20),
    config_hash character varying(64),
    abuse_level integer
);


--
-- Name: billing_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_transactions (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    ledger_id character varying(36) NOT NULL,
    cycle_year_month character varying(7) NOT NULL,
    plan_name character varying(50) NOT NULL,
    transaction_type character varying(30) NOT NULL,
    addon_tokens_added bigint NOT NULL,
    amount_currency character varying(10) NOT NULL,
    amount_value numeric(12,2) NOT NULL,
    triggered_by character varying(20) NOT NULL,
    reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: bot_knowledge_bases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_knowledge_bases (
    bot_id character varying(36) NOT NULL,
    knowledge_base_id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: bot_workers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_workers (
    id character varying(36) NOT NULL,
    bot_id character varying(36) NOT NULL,
    name character varying(100) NOT NULL,
    description text NOT NULL,
    worker_prompt text NOT NULL,
    llm_provider character varying(50),
    llm_model character varying(100),
    temperature double precision NOT NULL,
    max_tokens integer NOT NULL,
    max_tool_calls integer NOT NULL,
    enabled_mcp_ids json NOT NULL,
    knowledge_base_ids json NOT NULL,
    sort_order integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    tool_configs json DEFAULT '{}'::json NOT NULL,
    enabled_tools json,
    direct_retrieval boolean DEFAULT false NOT NULL
);




--
-- Name: bots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bots (
    id character varying(36) NOT NULL,
    short_code character varying(16) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(1000) NOT NULL,
    is_active boolean NOT NULL,
    bot_prompt text NOT NULL,
    enabled_tools json NOT NULL,
    llm_provider character varying(50) NOT NULL,
    llm_model character varying(100) NOT NULL,
    show_sources boolean DEFAULT true NOT NULL,
    mcp_servers json NOT NULL,
    mcp_bindings json NOT NULL,
    max_tool_calls integer NOT NULL,
    eval_provider character varying(50),
    eval_model character varying(100),
    eval_depth character varying(20) DEFAULT 'L1'::character varying NOT NULL,
    base_prompt text NOT NULL,
    fab_icon_url character varying(512) DEFAULT ''::character varying NOT NULL,
    widget_enabled boolean NOT NULL,
    widget_allowed_origins json NOT NULL,
    widget_keep_history boolean NOT NULL,
    widget_welcome_message character varying(500) NOT NULL,
    widget_placeholder_text character varying(200) NOT NULL,
    widget_greeting_messages json NOT NULL,
    widget_greeting_animation character varying(20) NOT NULL,
    memory_enabled boolean DEFAULT false NOT NULL,
    memory_extraction_threshold integer DEFAULT 3 NOT NULL,
    memory_extraction_prompt text DEFAULT ''::text NOT NULL,
    rerank_enabled boolean DEFAULT false NOT NULL,
    rerank_model character varying(100) DEFAULT ''::character varying NOT NULL,
    rerank_top_n integer DEFAULT 20 NOT NULL,
    rerank_final_top_k integer DEFAULT 5 NOT NULL,
    intent_routes json DEFAULT '[]'::json NOT NULL,
    router_model character varying(100) DEFAULT ''::character varying NOT NULL,
    busy_reply_message character varying(500) DEFAULT '小編正在努力回覆中，請稍等一下喔～'::character varying NOT NULL,
    line_channel_secret character varying(255),
    line_channel_access_token character varying(255),
    line_show_sources boolean DEFAULT false NOT NULL,
    temperature double precision NOT NULL,
    max_tokens integer NOT NULL,
    history_limit integer NOT NULL,
    frequency_penalty double precision NOT NULL,
    reasoning_effort character varying(10) NOT NULL,
    rag_top_k integer NOT NULL,
    rag_score_threshold double precision NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    tool_configs json DEFAULT '{}'::json NOT NULL,
    customer_service_url character varying(512) DEFAULT ''::character varying NOT NULL,
    summary_model character varying(100) DEFAULT ''::character varying NOT NULL,
    rag_retrieval_modes jsonb DEFAULT '["raw"]'::jsonb NOT NULL,
    query_rewrite_enabled boolean DEFAULT false NOT NULL,
    query_rewrite_model character varying(100) DEFAULT ''::character varying NOT NULL,
    query_rewrite_extra_hint text DEFAULT ''::text NOT NULL,
    hyde_enabled boolean DEFAULT false NOT NULL,
    hyde_model character varying(100) DEFAULT ''::character varying NOT NULL,
    hyde_extra_hint text DEFAULT ''::text NOT NULL,
    mode character varying(10) DEFAULT 'deep'::character varying NOT NULL,
    gate_mode character varying(10) DEFAULT 'off'::character varying NOT NULL,
    gate_soft_threshold double precision DEFAULT 0.8 NOT NULL,
    gate_repeats integer DEFAULT 3 NOT NULL,
    gate_auto_publish boolean DEFAULT false NOT NULL,
    gate_daily_limit integer DEFAULT 20 NOT NULL,
    gate_budget_usd double precision DEFAULT 1.0 NOT NULL,
    gate_excluded_cases jsonb DEFAULT '[]'::jsonb NOT NULL
);

--
-- Name: bot_config_versions; Type: TABLE; Schema: public; Owner: -
-- Issue #54 Phase A — Bot 設定整包版控（migrations/add_bot_config_versions.sql）
--

CREATE TABLE public.bot_config_versions (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    bot_id character varying(36) NOT NULL,
    version_no integer NOT NULL,
    config_snapshot jsonb NOT NULL,
    snapshot_schema integer DEFAULT 1 NOT NULL,
    changed_fields jsonb DEFAULT '[]'::jsonb NOT NULL,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    is_current boolean DEFAULT false NOT NULL,
    source character varying(20) DEFAULT 'manual'::character varying NOT NULL,
    source_run_id character varying(36),
    gate_run_id character varying(36),
    gate_verdict character varying(20),
    author_user_id text,
    published_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT bot_config_versions_pkey PRIMARY KEY (id),
    CONSTRAINT uq_bcv_bot_version UNIQUE (bot_id, version_no)
);

CREATE INDEX ix_bcv_bot_created ON public.bot_config_versions
    USING btree (bot_id, created_at DESC);
CREATE INDEX ix_bcv_tenant ON public.bot_config_versions
    USING btree (tenant_id);
CREATE UNIQUE INDEX ix_bcv_current ON public.bot_config_versions
    USING btree (bot_id) WHERE is_current;


--
-- Name: built_in_tools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.built_in_tools (
    name character varying(64) NOT NULL,
    label character varying(128) NOT NULL,
    description character varying(2000) DEFAULT ''::character varying NOT NULL,
    requires_kb boolean DEFAULT false NOT NULL,
    scope character varying(20) DEFAULT 'global'::character varying NOT NULL,
    tenant_ids json DEFAULT '[]'::json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: chunk_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunk_categories (
    id character varying(36) NOT NULL,
    kb_id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    name character varying(200) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    chunk_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunks (
    id character varying(36) NOT NULL,
    document_id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    content text NOT NULL,
    chunk_index integer NOT NULL,
    metadata json NOT NULL,
    quality_flag character varying(20),
    context_text text DEFAULT ''::text NOT NULL,
    category_id character varying(36)
);


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    bot_id character varying(36),
    visitor_id character varying(128),
    created_at timestamp with time zone NOT NULL,
    summary text,
    message_count integer DEFAULT 0 NOT NULL,
    summary_message_count integer,
    last_message_at timestamp with time zone,
    summary_at timestamp with time zone
);


--
-- Name: diagnostic_rules_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.diagnostic_rules_configs (
    id character varying(36) NOT NULL,
    single_rules json,
    combo_rules json,
    updated_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id character varying(36) NOT NULL,
    kb_id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    filename character varying(500) NOT NULL,
    content_type character varying(255) NOT NULL,
    content text NOT NULL,
    raw_content bytea,
    storage_path character varying(1000) NOT NULL,
    status character varying(50) NOT NULL,
    chunk_count integer NOT NULL,
    avg_chunk_length integer NOT NULL,
    min_chunk_length integer NOT NULL,
    max_chunk_length integer NOT NULL,
    quality_score double precision NOT NULL,
    quality_issues text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    parent_id character varying(36),
    page_number integer,
    source character varying(64) DEFAULT ''::character varying NOT NULL,
    source_id character varying(128) DEFAULT ''::character varying NOT NULL
);


--
-- Name: error_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.error_events (
    id character varying(36) NOT NULL,
    fingerprint character varying(16) NOT NULL,
    source character varying(20) NOT NULL,
    error_type character varying(200) NOT NULL,
    message text NOT NULL,
    stack_trace text,
    request_id character varying(20),
    path character varying(500),
    method character varying(10),
    status_code integer,
    tenant_id character varying(36),
    user_agent text,
    extra json,
    resolved boolean NOT NULL,
    resolved_at timestamp with time zone,
    resolved_by character varying(200),
    created_at timestamp with time zone NOT NULL
);


--
-- Name: error_notification_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.error_notification_logs (
    id character varying(36) NOT NULL,
    fingerprint character varying(16) NOT NULL,
    channel_id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feedback (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    conversation_id character varying(36) NOT NULL,
    message_id character varying(36) NOT NULL,
    user_id character varying(100),
    channel character varying(20) NOT NULL,
    rating character varying(20) NOT NULL,
    comment text,
    tags text NOT NULL,
    retrieval_quality character varying(20),
    created_at timestamp with time zone NOT NULL
);


--
-- Name: guard_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guard_logs (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    bot_id character varying(36),
    user_id character varying(36),
    log_type character varying(20) NOT NULL,
    rule_matched character varying(500) DEFAULT ''::character varying NOT NULL,
    user_message text DEFAULT ''::text NOT NULL,
    ai_response text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: guard_rules_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guard_rules_configs (
    id character varying(36) DEFAULT 'default'::character varying NOT NULL,
    input_rules jsonb DEFAULT '[]'::jsonb NOT NULL,
    output_keywords jsonb DEFAULT '[]'::jsonb NOT NULL,
    llm_guard_enabled boolean DEFAULT false NOT NULL,
    llm_guard_model character varying(100) DEFAULT ''::character varying NOT NULL,
    input_guard_prompt text DEFAULT ''::text NOT NULL,
    output_guard_prompt text DEFAULT ''::text NOT NULL,
    blocked_response text DEFAULT '我只能協助您處理客服相關問題。'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    llm_input_guard_enabled boolean DEFAULT false NOT NULL
);


--
-- Name: knowledge_bases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.knowledge_bases (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(1000) NOT NULL,
    kb_type character varying(20) DEFAULT 'user'::character varying NOT NULL,
    ocr_mode character varying(20) DEFAULT 'general'::character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    ocr_model character varying(100) DEFAULT ''::character varying NOT NULL,
    context_model character varying(100) DEFAULT ''::character varying NOT NULL,
    classification_model character varying(100) DEFAULT ''::character varying NOT NULL,
    embedding_model character varying(100) DEFAULT ''::character varying NOT NULL,
    chunk_strategy character varying(20) DEFAULT ''::character varying NOT NULL,
    dm_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    dm_metadata_model character varying(100) DEFAULT ''::character varying NOT NULL,
    ocr_slice_grid character varying(16) DEFAULT ''::character varying NOT NULL
);


--
-- Name: log_retention_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_retention_policies (
    id character varying(36) NOT NULL,
    enabled boolean NOT NULL,
    retention_days integer NOT NULL,
    cleanup_hour integer NOT NULL,
    cleanup_interval_hours integer NOT NULL,
    last_cleanup_at timestamp with time zone,
    deleted_count_last integer NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: mcp_server_registrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mcp_server_registrations (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(2000) NOT NULL,
    transport character varying(10) NOT NULL,
    url character varying(1000) NOT NULL,
    command character varying(500) NOT NULL,
    args json NOT NULL,
    required_env json NOT NULL,
    available_tools json NOT NULL,
    version character varying(50) NOT NULL,
    scope character varying(20) NOT NULL,
    tenant_ids json NOT NULL,
    is_enabled boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: memory_facts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memory_facts (
    id character varying(36) NOT NULL,
    profile_id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    memory_type character varying(20) DEFAULT 'long_term'::character varying NOT NULL,
    category character varying(30) DEFAULT 'custom'::character varying NOT NULL,
    key character varying(200) NOT NULL,
    value text NOT NULL,
    source_conversation_id character varying(36),
    confidence double precision DEFAULT '1'::double precision NOT NULL,
    last_accessed_at timestamp with time zone,
    expires_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id character varying(36) NOT NULL,
    conversation_id character varying(36) NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    tool_calls_json text NOT NULL,
    latency_ms integer,
    retrieved_chunks text,
    created_at timestamp with time zone NOT NULL,
    structured_content text
);


--
-- Name: model_pricing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_pricing (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider character varying(50) NOT NULL,
    model_id character varying(200) NOT NULL,
    display_name character varying(200) NOT NULL,
    category character varying(20) DEFAULT 'llm'::character varying NOT NULL,
    input_price numeric(12,6) NOT NULL,
    output_price numeric(12,6) NOT NULL,
    cache_read_price numeric(12,6) DEFAULT 0 NOT NULL,
    cache_creation_price numeric(12,6) DEFAULT 0 NOT NULL,
    effective_from timestamp with time zone NOT NULL,
    effective_to timestamp with time zone,
    created_by character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    note text,
    CONSTRAINT chk_effective_range CHECK (((effective_to IS NULL) OR (effective_to > effective_from))),
    CONSTRAINT chk_prices_non_negative CHECK (((input_price >= (0)::numeric) AND (output_price >= (0)::numeric) AND (cache_read_price >= (0)::numeric) AND (cache_creation_price >= (0)::numeric)))
);


--
-- Name: notification_channels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_channels (
    id character varying(36) NOT NULL,
    channel_type character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    enabled boolean NOT NULL,
    config_encrypted text NOT NULL,
    throttle_minutes integer NOT NULL,
    min_severity character varying(20) NOT NULL,
    notify_diagnostics boolean DEFAULT false NOT NULL,
    diagnostic_severity character varying(20) DEFAULT 'critical'::character varying NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL,
    notify_abuse boolean DEFAULT true NOT NULL
);


--
-- Name: outbox_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outbox_events (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    aggregate_type character varying(40) NOT NULL,
    aggregate_id character varying(64) NOT NULL,
    event_type character varying(40) NOT NULL,
    payload jsonb NOT NULL,
    doc_watermark_ts timestamp with time zone,
    status character varying(16) DEFAULT 'pending'::character varying NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 8 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    last_error text,
    locked_by character varying(64),
    locked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT chk_outbox_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying, 'done'::character varying, 'dead'::character varying])::text[])))
);


--
-- Name: plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plans (
    id character varying(36) NOT NULL,
    name character varying(50) NOT NULL,
    base_monthly_tokens bigint DEFAULT 0 NOT NULL,
    addon_pack_tokens bigint DEFAULT 0 NOT NULL,
    base_price numeric(10,2) DEFAULT 0 NOT NULL,
    addon_price numeric(10,2) DEFAULT 0 NOT NULL,
    currency character varying(3) DEFAULT 'TWD'::character varying NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pricing_recalc_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pricing_recalc_audit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    pricing_id uuid NOT NULL,
    recalc_from timestamp with time zone NOT NULL,
    recalc_to timestamp with time zone NOT NULL,
    affected_rows integer NOT NULL,
    cost_before_total numeric(15,6) NOT NULL,
    cost_after_total numeric(15,6) NOT NULL,
    executed_by character varying(100) NOT NULL,
    executed_at timestamp with time zone DEFAULT now() NOT NULL,
    reason text NOT NULL
);


--
-- Name: processing_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processing_tasks (
    id character varying(36) NOT NULL,
    document_id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    status character varying(50) NOT NULL,
    progress integer NOT NULL,
    error_message text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: provider_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.provider_settings (
    id character varying(36) NOT NULL,
    provider_type character varying(20) NOT NULL,
    provider_name character varying(50) NOT NULL,
    display_name character varying(255) NOT NULL,
    is_enabled boolean NOT NULL,
    api_key_encrypted text NOT NULL,
    base_url character varying(500) NOT NULL,
    models json NOT NULL,
    extra_config json NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: quota_alert_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quota_alert_logs (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    cycle_year_month character varying(7) NOT NULL,
    alert_type character varying(30) NOT NULL,
    used_ratio numeric(5,4) NOT NULL,
    message text,
    delivered_to_email boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rag_evaluations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rag_evaluations (
    id character varying(36) NOT NULL,
    eval_id character varying(36) NOT NULL,
    message_id character varying(36),
    trace_id character varying(36),
    tenant_id character varying(36) NOT NULL,
    layer character varying(20) NOT NULL,
    dimensions json,
    avg_score double precision NOT NULL,
    model_used character varying(200) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: rate_limit_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rate_limit_configs (
    id character varying(36) NOT NULL,
    tenant_id character varying(36),
    endpoint_group character varying(20) NOT NULL,
    requests_per_minute integer NOT NULL,
    burst_size integer NOT NULL,
    per_user_requests_per_minute integer,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: request_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.request_logs (
    id character varying(36) NOT NULL,
    request_id character varying(20) NOT NULL,
    method character varying(10) NOT NULL,
    path character varying(500) NOT NULL,
    status_code integer NOT NULL,
    elapsed_ms double precision NOT NULL,
    tenant_id character varying(36),
    error_detail text,
    trace_steps json,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: system_prompt_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_prompt_configs (
    id character varying(36) NOT NULL,
    system_prompt text NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    plan character varying(50) NOT NULL,
    monthly_token_limit integer,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    default_ocr_model character varying(100) DEFAULT ''::character varying NOT NULL,
    default_context_model character varying(100) DEFAULT ''::character varying NOT NULL,
    default_classification_model character varying(100) DEFAULT ''::character varying NOT NULL,
    included_categories jsonb,
    default_summary_model character varying(100) DEFAULT ''::character varying NOT NULL,
    default_intent_model character varying(100) DEFAULT ''::character varying NOT NULL,
    prompt_gate_enabled boolean DEFAULT false NOT NULL
);


--
-- Name: COLUMN tenants.included_categories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.included_categories IS 'NULL = 全部 category 計入額度；list = 只計入列表內的；[] = 全部不計入';


--
-- Name: token_ledger_topups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_ledger_topups (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    cycle_year_month character varying(7) NOT NULL,
    amount bigint NOT NULL,
    reason character varying(32) NOT NULL,
    pricing_version character varying(32),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: token_ledgers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_ledgers (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    cycle_year_month character varying(7) NOT NULL,
    plan_name character varying(50) NOT NULL,
    base_total bigint DEFAULT 0 NOT NULL,
    base_remaining bigint DEFAULT 0 NOT NULL,
    addon_remaining bigint DEFAULT 0 NOT NULL,
    total_used_in_cycle bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: token_usage_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_usage_records (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    request_type character varying(20) NOT NULL,
    model character varying(100) NOT NULL,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    estimated_cost double precision NOT NULL,
    cache_read_tokens integer NOT NULL,
    cache_creation_tokens integer NOT NULL,
    message_id character varying(36),
    bot_id character varying(36),
    created_at timestamp with time zone NOT NULL,
    cost_recalc_at timestamp with time zone,
    kb_id character varying(36),
    run_id character varying(36),
    config_version_id character varying(36),
    config_hash character varying(64)
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id character varying(36) NOT NULL,
    tenant_id character varying(36),
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    role character varying(20) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    token_version integer DEFAULT 1 NOT NULL
);


--
-- Name: visitor_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.visitor_identities (
    id character varying(36) NOT NULL,
    profile_id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    source character varying(20) NOT NULL,
    external_id character varying(200) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: visitor_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.visitor_profiles (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    display_name character varying(200),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: _applied_migrations _applied_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public._applied_migrations
    ADD CONSTRAINT _applied_migrations_pkey PRIMARY KEY (filename);


--
-- Name: agent_execution_traces agent_execution_traces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_execution_traces
    ADD CONSTRAINT agent_execution_traces_pkey PRIMARY KEY (id);


--
-- Name: agent_execution_traces agent_execution_traces_trace_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_execution_traces
    ADD CONSTRAINT agent_execution_traces_trace_id_key UNIQUE (trace_id);


--
-- Name: billing_transactions billing_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_transactions
    ADD CONSTRAINT billing_transactions_pkey PRIMARY KEY (id);


--
-- Name: bot_knowledge_bases bot_knowledge_bases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_knowledge_bases
    ADD CONSTRAINT bot_knowledge_bases_pkey PRIMARY KEY (bot_id, knowledge_base_id);


--
-- Name: bot_workers bot_workers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_workers
    ADD CONSTRAINT bot_workers_pkey PRIMARY KEY (id);


--
-- Name: bots bots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bots
    ADD CONSTRAINT bots_pkey PRIMARY KEY (id);


--
-- Name: bots bots_short_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bots
    ADD CONSTRAINT bots_short_code_key UNIQUE (short_code);


--
-- Name: built_in_tools built_in_tools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.built_in_tools
    ADD CONSTRAINT built_in_tools_pkey PRIMARY KEY (name);


--
-- Name: chunk_categories chunk_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_categories
    ADD CONSTRAINT chunk_categories_pkey PRIMARY KEY (id);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: diagnostic_rules_configs diagnostic_rules_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnostic_rules_configs
    ADD CONSTRAINT diagnostic_rules_configs_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: error_events error_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.error_events
    ADD CONSTRAINT error_events_pkey PRIMARY KEY (id);


--
-- Name: error_notification_logs error_notification_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.error_notification_logs
    ADD CONSTRAINT error_notification_logs_pkey PRIMARY KEY (id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (id);


--
-- Name: guard_logs guard_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guard_logs
    ADD CONSTRAINT guard_logs_pkey PRIMARY KEY (id);


--
-- Name: guard_rules_configs guard_rules_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guard_rules_configs
    ADD CONSTRAINT guard_rules_configs_pkey PRIMARY KEY (id);


--
-- Name: knowledge_bases knowledge_bases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_bases
    ADD CONSTRAINT knowledge_bases_pkey PRIMARY KEY (id);


--
-- Name: log_retention_policies log_retention_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_retention_policies
    ADD CONSTRAINT log_retention_policies_pkey PRIMARY KEY (id);


--
-- Name: mcp_server_registrations mcp_server_registrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mcp_server_registrations
    ADD CONSTRAINT mcp_server_registrations_pkey PRIMARY KEY (id);


--
-- Name: memory_facts memory_facts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_facts
    ADD CONSTRAINT memory_facts_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: model_pricing model_pricing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_pricing
    ADD CONSTRAINT model_pricing_pkey PRIMARY KEY (id);


--
-- Name: notification_channels notification_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_channels
    ADD CONSTRAINT notification_channels_pkey PRIMARY KEY (id);


--
-- Name: outbox_events outbox_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outbox_events
    ADD CONSTRAINT outbox_events_pkey PRIMARY KEY (id);


--
-- Name: plans plans_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plans
    ADD CONSTRAINT plans_name_key UNIQUE (name);


--
-- Name: plans plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plans
    ADD CONSTRAINT plans_pkey PRIMARY KEY (id);


--
-- Name: pricing_recalc_audit pricing_recalc_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pricing_recalc_audit
    ADD CONSTRAINT pricing_recalc_audit_pkey PRIMARY KEY (id);


--
-- Name: processing_tasks processing_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_tasks
    ADD CONSTRAINT processing_tasks_pkey PRIMARY KEY (id);


--
-- Name: provider_settings provider_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_settings
    ADD CONSTRAINT provider_settings_pkey PRIMARY KEY (id);


--
-- Name: quota_alert_logs quota_alert_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota_alert_logs
    ADD CONSTRAINT quota_alert_logs_pkey PRIMARY KEY (id);


--
-- Name: rag_evaluations rag_evaluations_eval_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rag_evaluations
    ADD CONSTRAINT rag_evaluations_eval_id_key UNIQUE (eval_id);


--
-- Name: rag_evaluations rag_evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rag_evaluations
    ADD CONSTRAINT rag_evaluations_pkey PRIMARY KEY (id);


--
-- Name: rate_limit_configs rate_limit_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limit_configs
    ADD CONSTRAINT rate_limit_configs_pkey PRIMARY KEY (id);


--
-- Name: request_logs request_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_logs
    ADD CONSTRAINT request_logs_pkey PRIMARY KEY (id);


--
-- Name: system_prompt_configs system_prompt_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_prompt_configs
    ADD CONSTRAINT system_prompt_configs_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_name_key UNIQUE (name);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: token_ledger_topups token_ledger_topups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_ledger_topups
    ADD CONSTRAINT token_ledger_topups_pkey PRIMARY KEY (id);


--
-- Name: token_ledgers token_ledgers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_ledgers
    ADD CONSTRAINT token_ledgers_pkey PRIMARY KEY (id);


--
-- Name: token_usage_records token_usage_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_usage_records
    ADD CONSTRAINT token_usage_records_pkey PRIMARY KEY (id);


--
-- Name: feedback uq_feedback_message; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT uq_feedback_message UNIQUE (message_id);


--
-- Name: visitor_identities uq_identity_lookup; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visitor_identities
    ADD CONSTRAINT uq_identity_lookup UNIQUE (tenant_id, source, external_id);


--
-- Name: token_ledgers uq_ledger_tenant_cycle; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_ledgers
    ADD CONSTRAINT uq_ledger_tenant_cycle UNIQUE (tenant_id, cycle_year_month);


--
-- Name: memory_facts uq_memory_fact_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_facts
    ADD CONSTRAINT uq_memory_fact_key UNIQUE (profile_id, key);


--
-- Name: provider_settings uq_provider_type_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_settings
    ADD CONSTRAINT uq_provider_type_name UNIQUE (provider_type, provider_name);


--
-- Name: quota_alert_logs uq_quota_alert_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota_alert_logs
    ADD CONSTRAINT uq_quota_alert_unique UNIQUE (tenant_id, cycle_year_month, alert_type);


--
-- Name: rate_limit_configs uq_rl_tenant_group; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limit_configs
    ADD CONSTRAINT uq_rl_tenant_group UNIQUE (tenant_id, endpoint_group);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: visitor_identities visitor_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visitor_identities
    ADD CONSTRAINT visitor_identities_pkey PRIMARY KEY (id);


--
-- Name: visitor_profiles visitor_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visitor_profiles
    ADD CONSTRAINT visitor_profiles_pkey PRIMARY KEY (id);


--
-- Name: idx_model_pricing_effective; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_pricing_effective ON public.model_pricing USING btree (effective_from DESC);


--
-- Name: idx_model_pricing_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_pricing_lookup ON public.model_pricing USING btree (provider, model_id, effective_from DESC);


--
-- Name: idx_pricing_recalc_audit_executed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pricing_recalc_audit_executed ON public.pricing_recalc_audit USING btree (executed_at DESC);


--
-- Name: ix_agent_exec_traces_bot_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_exec_traces_bot_id ON public.agent_execution_traces USING btree (bot_id);


--
-- Name: ix_billing_transactions_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_transactions_created ON public.billing_transactions USING btree (created_at DESC);


--
-- Name: ix_billing_transactions_tenant_cycle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_transactions_tenant_cycle ON public.billing_transactions USING btree (tenant_id, cycle_year_month);


--
-- Name: ix_built_in_tools_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_built_in_tools_scope ON public.built_in_tools USING btree (scope);


--
-- Name: ix_chunk_categories_kb_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chunk_categories_kb_id ON public.chunk_categories USING btree (kb_id);


--
-- Name: ix_conversations_pending_summary; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversations_pending_summary ON public.conversations USING btree (last_message_at) WHERE ((summary IS NULL) OR (summary_message_count < message_count));


--
-- Name: ix_documents_kb_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_kb_source ON public.documents USING btree (kb_id, source, source_id);


--
-- Name: ix_documents_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_parent_id ON public.documents USING btree (parent_id);


--
-- Name: ix_guard_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_guard_logs_created_at ON public.guard_logs USING btree (created_at DESC);


--
-- Name: ix_guard_logs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_guard_logs_tenant_id ON public.guard_logs USING btree (tenant_id);


--
-- Name: ix_outbox_aggregate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_outbox_aggregate ON public.outbox_events USING btree (aggregate_type, aggregate_id);


--
-- Name: ix_outbox_dlq; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_outbox_dlq ON public.outbox_events USING btree (status, created_at DESC) WHERE ((status)::text = 'dead'::text);


--
-- Name: ix_outbox_drain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_outbox_drain ON public.outbox_events USING btree (status, next_attempt_at) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying])::text[]));


--
-- Name: ix_plans_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plans_active ON public.plans USING btree (is_active);


--
-- Name: ix_quota_alert_logs_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quota_alert_logs_created ON public.quota_alert_logs USING btree (created_at DESC);


--
-- Name: ix_token_ledger_topups_tenant_cycle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_ledger_topups_tenant_cycle ON public.token_ledger_topups USING btree (tenant_id, cycle_year_month);


--
-- Name: ix_token_ledgers_tenant_cycle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_ledgers_tenant_cycle ON public.token_ledgers USING btree (tenant_id, cycle_year_month);


--
-- Name: ix_token_usage_records_tenant_kb_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_usage_records_tenant_kb_created ON public.token_usage_records USING btree (tenant_id, kb_id, created_at);


--
-- Name: ix_token_usage_records_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_usage_records_tenant_created ON public.token_usage_records USING btree (tenant_id, created_at);


--
-- Name: ix_token_usage_records_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_usage_records_message_id ON public.token_usage_records USING btree (message_id);


--
-- Name: ix_token_usage_records_tenant_bot_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_usage_records_tenant_bot_created ON public.token_usage_records USING btree (tenant_id, bot_id, created_at);


--
-- Name: ix_token_usage_records_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_usage_records_run_id ON public.token_usage_records USING btree (run_id);


--
-- Name: ix_traces_bot_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_traces_bot_created ON public.agent_execution_traces USING btree (bot_id, created_at DESC);


--
-- Name: ix_traces_outcome_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_traces_outcome_created ON public.agent_execution_traces USING btree (outcome, created_at DESC);


--
-- Name: ix_traces_tenant_conv_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_traces_tenant_conv_created ON public.agent_execution_traces USING btree (tenant_id, conversation_id, created_at DESC);


--
-- Name: billing_transactions billing_transactions_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_transactions
    ADD CONSTRAINT billing_transactions_ledger_id_fkey FOREIGN KEY (ledger_id) REFERENCES public.token_ledgers(id) ON DELETE CASCADE;


--
-- Name: billing_transactions billing_transactions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_transactions
    ADD CONSTRAINT billing_transactions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: bot_knowledge_bases bot_knowledge_bases_bot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_knowledge_bases
    ADD CONSTRAINT bot_knowledge_bases_bot_id_fkey FOREIGN KEY (bot_id) REFERENCES public.bots(id) ON DELETE CASCADE;


--
-- Name: bot_knowledge_bases bot_knowledge_bases_knowledge_base_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_knowledge_bases
    ADD CONSTRAINT bot_knowledge_bases_knowledge_base_id_fkey FOREIGN KEY (knowledge_base_id) REFERENCES public.knowledge_bases(id) ON DELETE CASCADE;


--
-- Name: bots bots_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bots
    ADD CONSTRAINT bots_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: chunk_categories chunk_categories_kb_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_categories
    ADD CONSTRAINT chunk_categories_kb_id_fkey FOREIGN KEY (kb_id) REFERENCES public.knowledge_bases(id) ON DELETE CASCADE;


--
-- Name: chunk_categories chunk_categories_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_categories
    ADD CONSTRAINT chunk_categories_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: chunks chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: chunks chunks_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: documents documents_kb_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_kb_id_fkey FOREIGN KEY (kb_id) REFERENCES public.knowledge_bases(id) ON DELETE CASCADE;


--
-- Name: documents documents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: knowledge_bases knowledge_bases_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_bases
    ADD CONSTRAINT knowledge_bases_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: memory_facts memory_facts_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_facts
    ADD CONSTRAINT memory_facts_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.visitor_profiles(id) ON DELETE CASCADE;


--
-- Name: pricing_recalc_audit pricing_recalc_audit_pricing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pricing_recalc_audit
    ADD CONSTRAINT pricing_recalc_audit_pricing_id_fkey FOREIGN KEY (pricing_id) REFERENCES public.model_pricing(id);


--
-- Name: processing_tasks processing_tasks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_tasks
    ADD CONSTRAINT processing_tasks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: processing_tasks processing_tasks_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_tasks
    ADD CONSTRAINT processing_tasks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: quota_alert_logs quota_alert_logs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quota_alert_logs
    ADD CONSTRAINT quota_alert_logs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: rate_limit_configs rate_limit_configs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limit_configs
    ADD CONSTRAINT rate_limit_configs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: token_ledger_topups token_ledger_topups_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_ledger_topups
    ADD CONSTRAINT token_ledger_topups_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: token_ledgers token_ledgers_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_ledgers
    ADD CONSTRAINT token_ledgers_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: users users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: visitor_identities visitor_identities_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visitor_identities
    ADD CONSTRAINT visitor_identities_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.visitor_profiles(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict QKlvJhIklbFIPUA8XbC0Nf7vIaW9SnqahESmB3a8cHI4r9OSGb5U96iCzOoRZMA



--
-- Issue #54 — prompt_optimizer / prompt gate 表（migrations:
-- gcp_sync_prompt_optimizer.sql + add_eval_gate_flags.sql +
-- add_prompt_gate_runs.sql；本區塊由 pg_dump 自 local-docker 取回，
-- 順帶修復 eval 表長期未同步 schema.sql 的 drift）
--

-- PostgreSQL database dump

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

-- Name: eval_datasets; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.eval_datasets (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    bot_id character varying(36),
    name character varying(200) NOT NULL,
    description text DEFAULT ''::text,
    target_prompt character varying(50) DEFAULT 'base_prompt'::character varying NOT NULL,
    agent_mode character varying(20) DEFAULT 'router'::character varying NOT NULL,
    default_assertions json,
    cost_config json,
    include_security boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_platform_base boolean DEFAULT false NOT NULL
);

-- Name: eval_test_cases; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.eval_test_cases (
    id character varying(36) NOT NULL,
    dataset_id character varying(36) NOT NULL,
    case_id character varying(100) NOT NULL,
    question text NOT NULL,
    priority character varying(5) DEFAULT 'P1'::character varying NOT NULL,
    category character varying(100) DEFAULT ''::character varying,
    conversation_history json,
    assertions json NOT NULL,
    tags json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    enabled boolean DEFAULT true NOT NULL
);

-- Name: prompt_gate_runs; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.prompt_gate_runs (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    bot_id character varying(36) NOT NULL,
    version_id character varying(36) NOT NULL,
    status character varying(20) DEFAULT 'queued'::character varying NOT NULL,
    verdict character varying(10),
    fail_reasons jsonb,
    dataset_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    repeats integer DEFAULT 3 NOT NULL,
    soft_threshold double precision DEFAULT 0.8 NOT NULL,
    total_cases integer,
    hard_failed_cases integer,
    soft_pass_rate double precision,
    unstable_cases integer,
    est_cost double precision,
    actual_cost double precision,
    input_tokens bigint,
    output_tokens bigint,
    details jsonb,
    error_message text,
    triggered_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone
);

-- Name: prompt_opt_runs; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.prompt_opt_runs (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    iteration integer NOT NULL,
    tenant_id character varying(36) NOT NULL,
    target_field character varying(50) NOT NULL,
    bot_id character varying(36),
    prompt_snapshot text NOT NULL,
    score double precision NOT NULL,
    passed_count integer NOT NULL,
    total_count integer NOT NULL,
    is_best boolean DEFAULT false,
    details json,
    created_at timestamp with time zone DEFAULT now()
);

-- Name: eval_datasets eval_datasets_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.eval_datasets
    ADD CONSTRAINT eval_datasets_pkey PRIMARY KEY (id);

-- Name: eval_test_cases eval_test_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.eval_test_cases
    ADD CONSTRAINT eval_test_cases_pkey PRIMARY KEY (id);

-- Name: prompt_gate_runs prompt_gate_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.prompt_gate_runs
    ADD CONSTRAINT prompt_gate_runs_pkey PRIMARY KEY (id);

-- Name: prompt_opt_runs prompt_opt_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.prompt_opt_runs
    ADD CONSTRAINT prompt_opt_runs_pkey PRIMARY KEY (id);

-- Name: ix_eval_datasets_bot_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_eval_datasets_bot_id ON public.eval_datasets USING btree (bot_id);

-- Name: ix_eval_datasets_tenant_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_eval_datasets_tenant_id ON public.eval_datasets USING btree (tenant_id);

-- Name: ix_eval_test_cases_dataset_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_eval_test_cases_dataset_id ON public.eval_test_cases USING btree (dataset_id);

-- Name: ix_pgr_bot_created; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_pgr_bot_created ON public.prompt_gate_runs USING btree (bot_id, created_at DESC);

-- Name: ix_pgr_tenant; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_pgr_tenant ON public.prompt_gate_runs USING btree (tenant_id);

-- Name: ix_prompt_opt_runs_bot_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_prompt_opt_runs_bot_id ON public.prompt_opt_runs USING btree (bot_id);

-- Name: ix_prompt_opt_runs_created_at; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_prompt_opt_runs_created_at ON public.prompt_opt_runs USING btree (created_at);

-- Name: ix_prompt_opt_runs_run_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_prompt_opt_runs_run_id ON public.prompt_opt_runs USING btree (run_id);

-- Name: eval_test_cases eval_test_cases_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.eval_test_cases
    ADD CONSTRAINT eval_test_cases_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.eval_datasets(id) ON DELETE CASCADE;

-- Name: prompt_gate_runs prompt_gate_runs_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.prompt_gate_runs
    ADD CONSTRAINT prompt_gate_runs_version_id_fkey FOREIGN KEY (version_id) REFERENCES public.bot_config_versions(id) ON DELETE CASCADE;

-- PostgreSQL database dump complete



--
-- Name: bot_config_versions bot_config_versions_bot_id_fkey; Type: FK CONSTRAINT
--

ALTER TABLE ONLY public.bot_config_versions
    ADD CONSTRAINT bot_config_versions_bot_id_fkey
    FOREIGN KEY (bot_id) REFERENCES public.bots(id) ON DELETE CASCADE;


-- Issue #60 — config_snapshots / audit_logs 主鍵與索引
ALTER TABLE ONLY public.config_snapshots
    ADD CONSTRAINT config_snapshots_pkey PRIMARY KEY (hash);
ALTER TABLE ONLY public.abuse_settings
    ADD CONSTRAINT abuse_settings_pkey PRIMARY KEY (id);


ALTER TABLE ONLY public.abuse_settings
    ADD CONSTRAINT uq_abuse_settings_scope UNIQUE (scope_kind, scope_id);


ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


CREATE INDEX ix_api_keys_tenant_id ON public.api_keys USING btree (tenant_id);


ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);
CREATE INDEX ix_audit_logs_entity ON public.audit_logs USING btree (entity_type, entity_id, created_at);
CREATE INDEX ix_audit_logs_tenant_created ON public.audit_logs USING btree (tenant_id, created_at);
CREATE INDEX ix_agent_execution_traces_bot_config_hash ON public.agent_execution_traces USING btree (bot_id, config_hash);
