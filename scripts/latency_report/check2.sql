SELECT to_char(t.created_at AT TIME ZONE 'Asia/Taipei', 'MM-DD HH24:MI') AS tm,
       t.source, round(t.total_ms) AS total_ms,
       string_agg(DISTINCT n->>'node_type', ',') AS node_types
FROM agent_execution_traces t, jsonb_array_elements(t.nodes::jsonb) n
WHERE t.created_at > now() - interval '2 days' AND t.source <> 'line'
GROUP BY t.trace_id, t.created_at, t.source, t.total_ms
ORDER BY t.created_at DESC LIMIT 20;
