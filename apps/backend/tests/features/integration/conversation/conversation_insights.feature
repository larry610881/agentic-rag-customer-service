Feature: Admin Conversation Insights Composite API
    身為系統/租戶管理員
    我想在一個對話上同時看到訊息、agent trace、token 用量
    以便 debug 與分析具體的對話脈絡

    Background:
        Given 租戶 "tenant-insights-A" 已存在
        And 租戶 "tenant-insights-A" 有 bot "bot-insights-1"
        And 租戶 "tenant-insights-A" 有 conversation "conv-001"
        And conversation "conv-001" 含 3 筆訊息（user/assistant/user）
        And conversation "conv-001" 有 2 筆 token_usage 記錄（各自帶 message_id）

    Scenario: 查某 conversation 的 messages 回傳該 conversation 所有訊息
        When system_admin 呼叫 GET /api/v1/admin/conversations/conv-001/messages
        Then 回應應為 200
        And 回應應包含 3 筆 messages
        And 每筆 message 應包含 role / content / created_at / message_id

    Scenario: tenant_admin 查他租戶的 conversation messages 回 404
        Given 另有租戶 "tenant-insights-B" 有 conversation "conv-other"
        When tenant_admin 以 "tenant-insights-A" 身份呼叫 GET /api/v1/admin/conversations/conv-other/messages
        Then 回應應為 404

    Scenario: system_admin 可跨租戶查 conversation messages
        Given 另有租戶 "tenant-insights-B" 有 conversation "conv-cross"
        When system_admin 呼叫 GET /api/v1/admin/conversations/conv-cross/messages
        Then 回應應為 200

    Scenario: 查 conversation 的 token usage 按 request_type 聚合
        When system_admin 呼叫 GET /api/v1/admin/conversations/conv-001/token-usage
        Then 回應應為 200
        And 回應應包含 totals 欄位（input_tokens / output_tokens / estimated_cost / message_count）
        And 回應應包含 by_request_type 陣列

    Scenario: 查不存在的 conversation_id 回 404
        When system_admin 呼叫 GET /api/v1/admin/conversations/non-existent/messages
        Then 回應應為 404

    Scenario: 空 conversation 的 token usage 回空聚合不 error
        Given 租戶 "tenant-insights-A" 有 conversation "conv-empty" 無任何 usage
        When system_admin 呼叫 GET /api/v1/admin/conversations/conv-empty/token-usage
        Then 回應應為 200
        And totals.message_count 應為 0
