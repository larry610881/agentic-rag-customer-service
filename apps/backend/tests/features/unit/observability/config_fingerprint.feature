Feature: 執行時設定指紋 (Runtime Config Fingerprint)
    身為紅隊鑑識人員
    我想要每一輪對話都以「當時實際生效的設定」算出指紋並可還原
    以便任一 trace 都能 join 出完整 snapshot，且設定沒變時不重複寫入

    Scenario: 相同有效設定不論欄位順序指紋相同
        Given 兩份內容相同但鍵順序不同的有效設定
        When 分別計算指紋
        Then 兩個指紋應相同且長度為 64

    Scenario: system prompt 多一個空白即為不同指紋
        Given 一份有效設定
        And 另一份只在 system_prompt 末尾多一個空白的有效設定
        When 分別計算指紋
        Then 兩個指紋應不同

    Scenario: snapshot 不含密鑰
        Given 一份有效設定其 guard 與 mcp 來源含 api_key 與 line_channel_access_token
        When 序列化為 snapshot
        Then snapshot 文字不應含 "sk-live" 也不應含 "line-token"

    Scenario: 首次紀錄寫入 repository，相同指紋第二次不再寫入
        Given 指紋紀錄器與可觀察的 repository
        When 對同一份有效設定紀錄兩次
        Then repository.ensure 應只被呼叫 1 次
        And 兩次回傳的指紋相同

    Scenario: repository 失敗時 fail-open 仍回傳指紋
        Given 指紋紀錄器且 repository.ensure 會拋例外
        When 對一份有效設定紀錄一次
        Then 仍應回傳長度 64 的指紋

    Scenario Outline: web / widget 對話 trace 帶有 config_hash
        Given 一個正常設定的 bot 與已注入的指紋紀錄器
        When 以來源 "<source>" 送出訊息並攔截 finish 的 trace
        Then trace.config_hash 應為長度 64 的字串
        And 回應的 config_hash 應與 trace.config_hash 相同
        And 紀錄器收到的有效設定 channel 應為 "<source>"

        Examples:
            | source |
            | web    |
            | widget |

    Scenario: LINE 對話 trace 帶有 config_hash 且 channel 為 line
        Given Bot "shop-a" 設定了 LINE Channel、Agent 回覆 "好的" 且已注入指紋紀錄器
        When 以 execute_for_bot 處理 LINE 文字事件並攔截 finish 的 trace
        Then trace.config_hash 應為長度 64 的字串
        And 紀錄器收到的有效設定 channel 應為 "line"

    Scenario: 兩份 snapshot 的 diff 只列出差異欄位
        Given 兩份 snapshot 僅 llm_model 與 kb_ids 不同
        When 計算 snapshot diff
        Then diff 應恰好含 "llm_model" 與 "retrieval.kb_ids" 兩個欄位並附 before/after
