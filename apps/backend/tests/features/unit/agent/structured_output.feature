Feature: 結構化輸出 — bot output_format 與供應商能力等級 (Structured Output)
    身為串接方
    我想要 bot 可指定輸出格式（一般 / 純文字 / JSON 附 schema）
    以便回應可直接被程式讀取，且依供應商能力做驗證與提醒

    Scenario Outline: 供應商 × 模型 → JSON 能力等級
        Given 供應商 "<provider>" 模型 "<model>"
        When 查詢結構化輸出能力
        Then 能力等級應為 "<tier>"

        Examples:
            | provider   | model                       | tier          |
            | openai     | gpt-4o                      | native_schema |
            | openai     | gpt-5.1                     | native_schema |
            | openai     | gpt-4-turbo                 | json_object   |
            | google     | gemini-3.7-flash            | native_schema |
            | google     | gemini-2.5-flash-lite       | native_schema |
            | anthropic  | claude-sonnet-4-5           | native_schema |
            | anthropic  | claude-3-5-haiku-20241022   | json_object   |
            | deepseek   | deepseek-chat               | json_object   |
            | qwen       | qwen-plus                   | json_object   |
            | ollama     | llama3.1                    | native_schema |
            | openrouter | anything                    | prompt_only   |
            | litellm    | anything                    | prompt_only   |
            | mock       | fake                        | prompt_only   |

    Scenario: 能力查詢端點回傳等級與說明
        Given 已登入的租戶管理員
        When 以 GET 查詢 "/api/v1/llm/structured-output-capability?provider=google&model=gemini-3.7-flash"
        Then 回應狀態應為 200
        And 回應 tier 應為 "native_schema"

    Scenario: output_format 值域驗證
        Given 一個既有的 bot
        When 將 bot output_format 更新為 "yaml"
        Then 結果應為 error

    Scenario: JSON 格式必須附合法的 JSON schema
        Given 一個既有的 bot
        When 將 bot output_format 更新為 "json" 且 schema 為 "not-a-schema"
        Then 結果應為 error

    Scenario: A 級供應商 — 請求夾帶 response schema
        Given 一個 mode 為 "kb"、output_format 為 "json" 且供應商為 "google" 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then Agent 應收到 llm_params 含 response_schema

    Scenario: B 級供應商 — 請求只要求 JSON 物件，schema 進 prompt
        Given 一個 mode 為 "kb"、output_format 為 "json" 且供應商為 "deepseek" 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then Agent 應收到 llm_params 含 response_json_object
        And Agent 收到的系統提示應含 schema 描述

    Scenario: JSON 回應通過驗證 — 放進 structured_content.output
        Given 一個 mode 為 "kb"、output_format 為 "json" 的 bot，模型回覆 '{"status":"km","category":"marketing","answer":"可以"}'
        When 以 web 送出訊息
        Then 回覆 structured_content.output 的 "status" 應為 "km"
        And 回覆內容應為合法 JSON

    Scenario: JSON 回應驗證失敗 — 重試一次後成功
        Given 一個 mode 為 "kb"、output_format 為 "json" 的 bot，模型第一次回覆 '不是 JSON'、第二次回覆 '{"status":"km","category":"marketing","answer":"可以"}'
        When 以 web 送出訊息
        Then Agent 應被呼叫 2 次
        And 回覆 structured_content.output 的 "status" 應為 "km"

    Scenario: JSON 回應驗證兩次都失敗 — 回未命中話術並記 trace
        Given 一個 mode 為 "kb"、output_format 為 "json" 且未命中話術為 '{"status":"error","answer":"請稍後再試"}' 的 bot，模型兩次都回覆 '不是 JSON'
        When 以 web 送出訊息
        Then 回覆內容應為合法 JSON
        And 回覆 structured_content.output 的 "answer" 應為 "請稍後再試"
        And 回覆 structured_content.display_text 應為 "請稍後再試"
        And trace 應含 status 為 "fallback" 的 "structured_output" 節點

    Scenario: 純文字格式 — 剝除 Markdown 符號
        Given 一個 mode 為 "kb"、output_format 為 "plain_text" 的 bot，模型回覆 '## 重點\n- **板橋店** 2 樓有快剪\n`備註`'
        When 以 web 送出訊息
        Then 回覆內容應為 "重點\n板橋店 2 樓有快剪\n備註"

    Scenario: LINE 通路的 JSON 格式 — 回覆預設輸出文字欄位 answer
        Given LINE 用例與 mode 為 "kb"、output_format 為 "json"、輸出文字欄位為預設值的 bot，模型回覆 '{"status":"km","category":"store-ops","answer":"配送每日兩班"}'
        When 系統處理一則 LINE 訊息
        Then LINE 回覆文字應為 "配送每日兩班"

    Scenario: 自訂輸出文字欄位 — LINE 顯示該欄位文字
        Given LINE 用例與 mode 為 "kb"、output_format 為 "json"、輸出文字欄位為 "reply" 的 bot，模型回覆 '{"reply":"配送每日兩班","status":"km"}'
        When 系統處理一則 LINE 訊息
        Then LINE 回覆文字應為 "配送每日兩班"

    Scenario: 自訂輸出文字欄位 — web structured_content.display_text
        Given 一個 mode 為 "kb"、output_format 為 "json"、輸出文字欄位為 "reply" 的 bot，模型回覆 '{"reply":"配送每日兩班","status":"km"}'
        When 以 web 送出訊息
        Then 回覆 structured_content.display_text 應為 "配送每日兩班"

    Scenario: JSON 格式未命中 — 回平台預設 JSON 未命中物件
        Given 一個 mode 為 "kb"、output_format 為 "json" 且未命中話術為 "-" 的 bot，檢索分數 0.10
        When 以 web 送出訊息
        Then 回覆內容應為合法 JSON
        And 回覆 structured_content.output 的 "status" 應為 "out_of_scope"
        And Agent 不應被呼叫

    Scenario: JSON 格式自訂未命中話術 — 儲存時必須是合法 JSON
        Given 一個既有的 bot
        When 將 bot output_format 更新為 "json" 且未命中話術為 '不是 JSON'
        Then 結果應為 error

    Scenario: JSON 格式自訂未命中話術 — 合法 JSON 可儲存
        Given 一個既有的 bot
        When 將 bot output_format 更新為 "json" 且未命中話術為 '{"status":"out_of_scope","answer":""}'
        Then 結果應為 saved

    Scenario: JSON 格式自訂未命中話術 — 不符 schema 時拒絕
        Given 一個既有的 bot
        When 將 bot output_format 更新為 "json"、schema 要求 "status" 欄位且未命中話術為 '{"answer":""}'
        Then 結果應為 error

    Scenario: 回覆附帶檢索統計 — 命中
        Given 一個 mode 為 "kb"、output_format 為 "text" 且未命中話術為 "-" 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then 回覆 structured_content.retrieval 的 top_score 應為 0.85 且 miss 應為 false

    Scenario: 回覆附帶檢索統計 — 未命中
        Given 一個 mode 為 "kb"、output_format 為 "text" 且未命中話術為 "-" 的 bot，檢索分數 0.10
        When 以 web 送出訊息
        Then 回覆 structured_content.retrieval 的 top_score 應為 0.1 且 miss 應為 true

    Scenario: deep 模式也可用 JSON 輸出（不限 kb）
        Given 一個 mode 為 "deep"、output_format 為 "json" 且供應商為 "openai" 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then Agent 應收到 llm_params 含 response_schema

    Scenario: 模型回覆夾雜說明文字 — 抓出第一個平衡的 JSON 物件（不需重試）
        Given 一個 mode 為 "kb"、output_format 為 "json" 的 bot，模型回覆 '好的，結果如下：```json\n{"status":"km","category":"a","answer":"可以"}\n``` 以上'
        When 以 web 送出訊息
        Then Agent 應被呼叫 1 次
        And 回覆 structured_content.output 的 "status" 應為 "km"
        And 回覆內容應為合法 JSON

    Scenario Outline: strict 相容性判定 — OpenAI / Gemini strict 模式只在 schema 相容時開
        Given 一個 "<kind>" 的 JSON schema
        When 判定 strict 相容性
        Then strict 應為 <strict>

        Examples:
            | kind         | strict |
            | closed       | true   |
            | open         | false  |
            | nested-open  | false  |
            | nested-closed| true   |
