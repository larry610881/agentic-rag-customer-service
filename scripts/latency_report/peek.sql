SELECT jsonb_pretty(n)
FROM agent_execution_traces t, jsonb_array_elements(t.nodes::jsonb) n
WHERE t.source='line' AND n->>'node_type'='user_input'
ORDER BY t.created_at DESC LIMIT 1;
