Feature: Tool Output 精確匹配 (Tool Output Matching)
    身為系統
    我需要將 ToolMessage 正確匹配到對應的 tool_call 記錄
    以便在同名工具多次呼叫時不會混淆

    Scenario: 使用 tool_call_id 精確匹配
        Given 有兩次 rag_query 工具呼叫記錄帶有不同 tool_call_id
        When 第一個 ToolMessage 帶有第一個 tool_call_id 回傳
        Then 第一個 tool_call 應有 tool_output
        And 第二個 tool_call 不應有 tool_output

    Scenario: tool_call_id 缺失時 fallback 到 tool_name 匹配
        Given 有兩次 rag_query 工具呼叫記錄無 tool_call_id
        When 一個 rag_query ToolMessage 回傳
        Then 最後一個無 output 的 rag_query 應被填充

    Scenario: 兩次同名工具呼叫都正確匹配
        Given 有兩次 rag_query 工具呼叫記錄帶有不同 tool_call_id
        When 兩個 ToolMessage 依序回傳帶有各自的 tool_call_id
        Then 兩個 tool_call 應各自有正確的 tool_output
