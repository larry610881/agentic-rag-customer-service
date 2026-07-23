SELECT to_char(t.created_at AT TIME ZONE 'Asia/Taipei', 'HH24:MI:SS') AS tm,
       max(n->'metadata'->>'message_preview') FILTER (WHERE n->>'node_type'='user_input') AS question,
       replace(max(n->>'label') FILTER (WHERE n->>'node_type'='worker_routing'), '✓ 分流結果：', '') AS worker,
       round(t.total_ms/100)/10.0 AS total_s,
       count(*) FILTER (WHERE n->>'node_type'='agent_llm') AS llm_calls,
       bool_or(n->>'node_type'='direct_retrieval') AS fast_path,
       bool_or(n->>'node_type'='escalated') AS escalated,
       max(n->'metadata'->>'top_score') FILTER (WHERE n->>'node_type'='direct_retrieval') AS top_score
FROM agent_execution_traces t, jsonb_array_elements(t.nodes::jsonb) n
WHERE t.source='line' AND t.created_at > timestamp '2026-07-23 06:10:00+00'
GROUP BY t.trace_id, t.created_at, t.total_ms
ORDER BY t.created_at;
