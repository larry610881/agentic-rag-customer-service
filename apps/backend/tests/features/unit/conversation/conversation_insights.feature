Feature: Conversation Insights Use Cases
    身為系統/租戶管理員
    我想查詢單一 conversation 的 messages 與 token 用量
    以便在對話與追蹤頁整合顯示

    Scenario: GetConversationMessagesUseCase 回傳 conversation 的所有訊息
        Given 一個 conversation "conv-A" 帶 3 筆 messages
        When system_admin 呼叫 GetConversationMessagesUseCase
        Then 結果應包含 3 筆 messages 與 conversation metadata

    Scenario: GetConversationMessagesUseCase 跨租戶查詢回 EntityNotFoundError
        Given 一個屬於租戶 "tenant-X" 的 conversation "conv-X"
        When tenant_admin 以 "tenant-Y" 身份呼叫
        Then 應拋出 EntityNotFoundError

    Scenario: GetConversationMessagesUseCase system_admin 可跨租戶
        Given 一個屬於租戶 "tenant-X" 的 conversation "conv-X"
        When system_admin 呼叫
        Then 結果應回傳該 conversation

    Scenario: GetConversationMessagesUseCase 不存在的 conversation 拋 EntityNotFoundError
        When system_admin 查不存在的 conversation "no-such"
        Then 應拋出 EntityNotFoundError

    Scenario: GetConversationTokenUsageUseCase 聚合 by_request_type 正確
        Given conversation "conv-T" 有 4 筆 usage (2 種 request_type)
        When system_admin 呼叫 GetConversationTokenUsageUseCase
        Then by_request_type 應有 2 筆聚合結果
        And totals.estimated_cost 應等於 4 筆加總

    Scenario: GetConversationTokenUsageUseCase 空 conversation 回空聚合
        Given conversation "conv-empty" 無任何 usage
        When system_admin 呼叫 GetConversationTokenUsageUseCase
        Then totals.message_count 應為 0
        And by_request_type 應為空陣列
