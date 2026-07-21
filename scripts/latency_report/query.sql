SELECT t.trace_id,
       to_char(t.created_at AT TIME ZONE 'Asia/Taipei', 'YYYY-MM-DD HH24:MI:SS') AS created_tw,
       round(t.total_ms) AS total_ms,
       t.llm_model,
       max(n->>'label') FILTER (WHERE n->>'node_type'='worker_routing') AS worker,
       round(min((n->>'start_ms')::float) FILTER (WHERE n->>'node_type'='agent_llm')) AS pre_agent_ms,
       round(sum((n->>'end_ms')::float - (n->>'start_ms')::float) FILTER (WHERE n->>'node_type'='agent_llm')) AS llm_total_ms,
       count(*) FILTER (WHERE n->>'node_type'='agent_llm') AS llm_calls,
       round(sum((n->>'end_ms')::float - (n->>'start_ms')::float) FILTER (WHERE n->>'node_type'='tool_call')) AS tool_ms,
       round(t.total_ms - max((n->>'end_ms')::float)) AS tail_ms,
       max(t.total_tokens->>'input_tokens') AS input_tokens,
       max(t.total_tokens->>'output_tokens') AS output_tokens
FROM agent_execution_traces t, jsonb_array_elements(t.nodes::jsonb) n
WHERE t.source='line' AND t.created_at > now() - interval '14 days'
GROUP BY t.trace_id, t.created_at, t.total_ms, t.llm_model
ORDER BY t.created_at;
