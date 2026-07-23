SELECT to_char(t.created_at AT TIME ZONE 'Asia/Taipei', 'HH24:MI:SS') AS tm,
       replace(max(n->>'label') FILTER (WHERE n->>'node_type'='worker_routing'), '✓ 分流結果：', '') AS worker,
       max(n->>'label') FILTER (WHERE n->>'node_type'='tool_call') AS tool_used,
       round(t.total_ms/100)/10.0 AS total_s
FROM agent_execution_traces t, jsonb_array_elements(t.nodes::jsonb) n
WHERE t.source='line' AND t.created_at > timestamp '2026-07-23 06:42:00+00'
GROUP BY t.trace_id, t.created_at, t.total_ms
ORDER BY t.created_at;
