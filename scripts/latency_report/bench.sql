SELECT to_char(t.created_at AT TIME ZONE 'Asia/Taipei', 'MM-DD HH24:MI') AS tm,
       max(n->>'label') FILTER (WHERE n->>'node_type'='worker_routing') AS worker,
       round(t.total_ms) AS total_ms,
       count(*) FILTER (WHERE n->>'node_type'='agent_llm') AS llm_calls,
       max(n->'metadata'->>'message_preview') FILTER (WHERE n->>'node_type'='user_input') AS question
FROM agent_execution_traces t, jsonb_array_elements(t.nodes::jsonb) n
WHERE t.source='line' AND t.created_at > now() - interval '14 days'
GROUP BY t.trace_id, t.created_at, t.total_ms
HAVING count(*) FILTER (WHERE n->>'node_type'='agent_llm') >= 2
ORDER BY t.total_ms DESC;
