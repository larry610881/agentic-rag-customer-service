SELECT t.trace_id,
       to_char(t.created_at AT TIME ZONE 'Asia/Taipei', 'YYYY-MM-DD HH24:MI:SS') AS created_tw,
       t.source,
       t.llm_model,
       round(t.total_ms) AS total_ms,
       round(min((n->>'start_ms')::float) FILTER (WHERE n->>'node_type'='first_token')) AS first_token_ms,
       round(max((n->>'start_ms')::float) FILTER (WHERE n->>'node_type'='first_token')) AS last_gen_first_token_ms,
       count(*) FILTER (WHERE n->>'node_type'='first_token') AS ft_nodes,
       round(sum((n->>'end_ms')::float - (n->>'start_ms')::float) FILTER (WHERE n->>'node_type'='agent_llm')) AS llm_total_ms,
       round(sum((n->>'end_ms')::float - (n->>'start_ms')::float) FILTER (WHERE n->>'node_type'='tool_call')) AS tool_ms
FROM agent_execution_traces t, jsonb_array_elements(t.nodes::jsonb) n
WHERE t.created_at > now() - interval '2 days'
GROUP BY t.trace_id, t.created_at, t.source, t.llm_model, t.total_ms
HAVING count(*) FILTER (WHERE n->>'node_type'='first_token') > 0
ORDER BY t.created_at;
