-- Platform Seed Data (PostgreSQL)
-- Tables: tenants, users, knowledge_bases, bots, bot_knowledge_bases,
--         provider_settings, system_prompt_configs, mcp_server_registrations

BEGIN;
SET session_replication_role = 'replica';

-- tenants (7 columns)
INSERT INTO tenants (id, name, plan, allowed_agent_modes, monthly_token_limit, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000000', '系統', 'system', '["router", "react", "supervisor"]', NULL, '2026-03-16 05:52:21', '2026-03-16 05:52:21')
ON CONFLICT (id) DO NOTHING;

-- users (7 columns)
INSERT INTO users (id, tenant_id, email, hashed_password, role, created_at, updated_at)
VALUES ('5bf59050-301c-4537-9054-a0447e5c29dc', '00000000-0000-0000-0000-000000000000', 'admin@system.com', '$2b$12$JzDlsghvEkXcTL2qmiFc4e00097.jCxHziuFZvZd9qyjMU/UT3NV6', 'system_admin', '2026-03-16 05:52:21', '2026-03-16 05:52:21')
ON CONFLICT (id) DO NOTHING;

-- knowledge_bases (7 columns)
INSERT INTO knowledge_bases (id, tenant_id, name, description, kb_type, created_at, updated_at)
VALUES ('99cfb632-a195-4d08-a80a-924cfc08173d', '00000000-0000-0000-0000-000000000000', '窩廚房', 'demo', 'user', '2026-03-17 01:10:59', '2026-03-17 01:10:59')
ON CONFLICT (id) DO NOTHING;

-- bots (45 columns)
INSERT INTO bots (id, short_code, tenant_id, name, description, is_active, system_prompt, enabled_tools, llm_provider, llm_model, show_sources, agent_mode, mcp_servers, mcp_bindings, max_tool_calls, audit_mode, eval_provider, eval_model, eval_depth, base_prompt, router_prompt, react_prompt, fab_icon_url, widget_enabled, widget_allowed_origins, widget_keep_history, widget_welcome_message, widget_placeholder_text, widget_greeting_messages, widget_greeting_animation, memory_enabled, memory_extraction_threshold, memory_extraction_prompt, busy_reply_message, line_channel_secret, line_channel_access_token, temperature, max_tokens, history_limit, frequency_penalty, reasoning_effort, rag_top_k, rag_score_threshold, created_at, updated_at)
VALUES ('100492a9-e711-4dab-a3a0-67ef33a4e3e2', 'IJgMCORo', '00000000-0000-0000-0000-000000000000', '測試工具', '', true, '', '["rag_query"]', 'openai', 'gpt-5.1', true, 'react', '[{"url": "", "name": "npx", "enabled_tools": ["weather_forecast", "weather_archive", "air_quality", "marine_weather", "elevation", "flood_forecast", "seasonal_forecast", "climate_projection", "ensemble_forecast", "geocoding", "dwd_icon_forecast", "gfs_forecast", "meteofrance_forecast", "ecmwf_forecast", "jma_forecast", "metno_forecast", "gem_forecast"], "tools": [], "version": ""}]', '[]', 5, 'off', '', '', 'L1', '', '', '', '', false, '[]', true, '', '', '[]', 'fade', false, 3, '', '小編正在努力回覆中，請稍等一下喔～', NULL, NULL, 0.3, 1024, 10, 0, 'medium', 5, 0.3, '2026-03-17 02:05:23', '2026-03-17 02:47:13')
ON CONFLICT (id) DO NOTHING;

INSERT INTO bots (id, short_code, tenant_id, name, description, is_active, system_prompt, enabled_tools, llm_provider, llm_model, show_sources, agent_mode, mcp_servers, mcp_bindings, max_tool_calls, audit_mode, eval_provider, eval_model, eval_depth, base_prompt, router_prompt, react_prompt, fab_icon_url, widget_enabled, widget_allowed_origins, widget_keep_history, widget_welcome_message, widget_placeholder_text, widget_greeting_messages, widget_greeting_animation, memory_enabled, memory_extraction_threshold, memory_extraction_prompt, busy_reply_message, line_channel_secret, line_channel_access_token, temperature, max_tokens, history_limit, frequency_penalty, reasoning_effort, rag_top_k, rag_score_threshold, created_at, updated_at)
VALUES ('86441a14-8940-45db-8bdf-00f4396363ad', 'SpOwiz2x', '00000000-0000-0000-0000-000000000000', '窩廚房客服', 'DEMO
', true, '# 窩小幫 — 桂冠窩廚房智慧客服助手

## 角色
你是「窩小幫」，桂冠窩廚房（Joy''in Kitchen）的智慧客服助手。品牌理念：「簡單做、開心吃」，提供料理課程、食譜、窩廚房自有商品。

## 回答準則
- 語氣親切溫暖，像熱愛料理的朋友聊天，使用繁體中文
- 適度用「～」「！」增加親和力，不要生硬客服口吻
- **回答控制在 50～100 字，能一句話說完就不要兩句**
- 需要列舉多項資訊時（如多堂課程），最多 150 字，用條列呈現
- 先直接回答 → 有需要再延伸推薦 1 個相關內容（不要每次都推）', '["rag_query"]', 'openai', 'gpt-5.1', false, 'react', '[{"url": "http://localhost:9000/mcp", "name": "http://localhost:9000/mcp", "enabled_tools": ["search_products", "search_courses"], "tools": [], "version": ""}]', '[]', 5, 'full', 'openai', 'gpt-5.1', 'L1+L2+L3', '', '', '', '', true, '["http://localhost:7777"]', true, '', '', '["歡迎來到窩廚房~"]', 'fade', false, 3, '', '窩小幫正在努力回覆中，請稍等一下喔～', NULL, NULL, 0.3, 1024, 10, 0, 'medium', 5, 0.3, '2026-03-17 01:12:19', '2026-03-17 02:28:47')
ON CONFLICT (id) DO NOTHING;

-- bot_knowledge_bases (3 columns)
INSERT INTO bot_knowledge_bases (bot_id, knowledge_base_id, created_at)
VALUES ('86441a14-8940-45db-8bdf-00f4396363ad', '99cfb632-a195-4d08-a80a-924cfc08173d', '2026-03-17 02:28:47')
ON CONFLICT DO NOTHING;
INSERT INTO bot_knowledge_bases (bot_id, knowledge_base_id, created_at)
VALUES ('100492a9-e711-4dab-a3a0-67ef33a4e3e2', '99cfb632-a195-4d08-a80a-924cfc08173d', '2026-03-17 02:47:13')
ON CONFLICT DO NOTHING;

-- mcp_server_registrations (15 columns)
INSERT INTO mcp_server_registrations (id, name, description, transport, url, command, args, required_env, available_tools, version, scope, tenant_ids, is_enabled, created_at, updated_at)
VALUES ('ecfb9372-3043-4b25-a368-295bb7e39279', 'http://localhost:9000/mcp', '', 'http', 'http://localhost:9000/mcp', '', '[]', '[]', '[{"name": "search_products", "description": "商品查詢"}, {"name": "search_courses", "description": "課程查詢"}]', '', 'global', '[]', true, '2026-03-17 01:14:41', '2026-03-17 01:14:41')
ON CONFLICT (id) DO NOTHING;

-- provider_settings (11 columns)
INSERT INTO provider_settings (id, provider_type, provider_name, display_name, is_enabled, api_key_encrypted, base_url, models, extra_config, created_at, updated_at)
VALUES ('2b30c3fb-f186-459a-be50-75bba780724e', 'llm', 'google', 'Google', false, '', '', '[{"model_id": "gemini-3.1-pro-preview", "display_name": "Gemini 3.1 Pro", "is_default": true, "is_enabled": true, "price": "$2/$12", "description": "", "input_price": 2.0, "output_price": 12.0}]', '{}', '2026-03-16 05:52:21', '2026-03-17 01:10:22')
ON CONFLICT (id) DO NOTHING;

INSERT INTO provider_settings (id, provider_type, provider_name, display_name, is_enabled, api_key_encrypted, base_url, models, extra_config, created_at, updated_at)
VALUES ('07f644ed-e861-4292-8b03-e2006291a758', 'llm', 'anthropic', 'Anthropic', false, '', '', '[{"model_id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6", "is_default": true, "is_enabled": true, "price": "$3/$15", "description": "", "input_price": 3.0, "output_price": 15.0}, {"model_id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "is_default": false, "is_enabled": true, "price": "$1/$5", "description": "", "input_price": 1.0, "output_price": 5.0}, {"model_id": "claude-opus-4-6", "display_name": "Claude Opus 4.6", "is_default": false, "is_enabled": true, "price": "$5/$25", "description": "", "input_price": 5.0, "output_price": 25.0}]', '{}', '2026-03-16 05:52:21', '2026-03-17 01:10:24')
ON CONFLICT (id) DO NOTHING;

INSERT INTO provider_settings (id, provider_type, provider_name, display_name, is_enabled, api_key_encrypted, base_url, models, extra_config, created_at, updated_at)
VALUES ('d2e949ad-a393-4710-9857-13cd2e80b97e', 'embedding', 'openai', 'OpenAI Embedding', true, 'm7AR2E4Urs0U9ZPcJfUKaP8+784dpPkAD+3ZObgmbxuqjGI56Np6IdPxFhTGk93bSv6iI88CMddSjUdw7VqPbEmsWcjrnhl+dumFRZM+LKCnojaE8YjYnqvoRvB/fXlTYdoztHeYD2MtBhtMLv7sO7a0Jmx1KnCVIxCoLt/ygAU2TjpXHvTX58GFHSzgnr7qj9R8BO8lANZ78HT6wqXTLoFQjNGmksSTfgAhaSYp504HwO/SMo6RsMyY5R28TYOj', '', '[{"model_id": "text-embedding-3-small", "display_name": "text-embedding-3-small", "is_default": true, "is_enabled": true, "price": "", "description": "", "input_price": 0, "output_price": 0}]', '{}', '2026-03-16 05:52:21', '2026-03-17 01:10:45')
ON CONFLICT (id) DO NOTHING;

INSERT INTO provider_settings (id, provider_type, provider_name, display_name, is_enabled, api_key_encrypted, base_url, models, extra_config, created_at, updated_at)
VALUES ('632fbeaa-65bd-4328-9939-0ca63b167fa1', 'llm', 'openai', 'OpenAI', true, 'T7qPabZ+IY84DfSCfAo75BEKAB4S4+dhKBnVyvg1AwsSceYUosKDqlzCWoF4xi9hJHUv5Fk+LQMvaw7nYMJ9bwWCdmMViviYe5cXfO63nDKnKBAXUuRwjP23euvHA00jbk6nhYBBHnTGNUXhzp82CsHMVzJAvzqdSJDDcTXgm3HdaaIbafLtyyQz65uEnuF+SEs/uDTtqe4k9HVZ1kw+KInw6yLG2ElzB14DmttM+fadeG0EpEtzGDtnvquL7i9n', '', '[{"model_id": "gpt-5.2", "display_name": "GPT-5.2", "is_default": true, "is_enabled": true, "price": "$1.75/$14", "description": "", "input_price": 1.75, "output_price": 14.0}, {"model_id": "gpt-5.1", "display_name": "GPT-5.1", "is_default": false, "is_enabled": true, "price": "$1.25/$10", "description": "", "input_price": 1.25, "output_price": 10.0}, {"model_id": "gpt-5", "display_name": "GPT-5", "is_default": false, "is_enabled": true, "price": "$1.25/$10", "description": "", "input_price": 1.25, "output_price": 10.0}, {"model_id": "gpt-5-mini", "display_name": "GPT-5 Mini", "is_default": false, "is_enabled": true, "price": "$0.25/$2", "description": "", "input_price": 0.25, "output_price": 2.0}, {"model_id": "gpt-5-nano", "display_name": "GPT-5 Nano", "is_default": false, "is_enabled": true, "price": "$0.05/$0.40", "description": "", "input_price": 0.05, "output_price": 0.4}]', '{}', '2026-03-16 05:52:21', '2026-03-17 01:10:45')
ON CONFLICT (id) DO NOTHING;

INSERT INTO provider_settings (id, provider_type, provider_name, display_name, is_enabled, api_key_encrypted, base_url, models, extra_config, created_at, updated_at)
VALUES ('82950ca1-dc14-4980-a892-388a0cda08df', 'llm', 'deepseek', 'DeepSeek', false, '', '', '[{"model_id": "deepseek-chat", "display_name": "DeepSeek V3.2", "is_default": true, "is_enabled": true, "price": "$0.27/$1.10", "description": "", "input_price": 0.27, "output_price": 1.1}, {"model_id": "deepseek-reasoner", "display_name": "DeepSeek R1", "is_default": false, "is_enabled": false, "price": "$0.55/$2.19", "description": "", "input_price": 0.55, "output_price": 2.19}]', '{}', '2026-03-16 05:52:21', '2026-03-17 01:10:47')
ON CONFLICT (id) DO NOTHING;

-- system_prompt_configs (5 columns)
INSERT INTO system_prompt_configs (id, base_prompt, router_mode_prompt, react_mode_prompt, updated_at)
VALUES ('default', '你是一個專業的客服助手，用友善且專業的語氣與用戶對話。
行為準則：
1. 回答必須基於提供的工具結果或知識庫內容，不可自行編造或幻覺。
2. 如果沒有相關資訊，誠實告知用戶，不要強行引用不相關的內容。
3. 回答應簡潔完整，避免冗餘但不遺漏重要資訊。
4. 保持一致的品牌語調，親切但專業。
5.今天是{today}', '如果有提供工具結果，請根據工具結果回答用戶的問題，確保準確、完整。
如果沒有工具結果，或工具結果與用戶問題無關，請自然地回應用戶（例如打招呼、閒聊）。', '推理策略：
1. 你擁有多個工具可以查詢即時資料（課程、商品、知識庫等）。收到用戶問題後，優先考慮是否需要呼叫工具取得最新資訊。
2. 涉及課程、商品、價格、名額、時間、講師等具體資訊時，必須使用工具查詢，不可憑記憶回答。
3. 每次只呼叫必要的工具，避免重複查詢相同內容。同一個工具不要用不同參數重複呼叫。
4. 綜合所有工具結果後，生成最終回答。若工具結果不足以回答問題，誠實告知用戶。', '2026-03-17 01:31:29')
ON CONFLICT (id) DO NOTHING;

SET session_replication_role = 'origin';
COMMIT;
