Feature: 租戶 API key 機器憑證 (Tenant API Key)
    身為租戶管理員
    我想要為外部系統簽發只綁我租戶、限定 bot 與 scope 的機器憑證
    以便外部 agent 串接時不必共用人類帳號，且撤銷即刻生效

    # --- domain ---

    Scenario: 建立 key 只回傳一次 secret，資料庫只存雜湊與前綴
        Given 租戶 "t1" 的 API key 建立命令 名稱 "看板" scopes "chat:send chat:history:read"
        When 執行建立 API key
        Then 回傳的 secret 以 "ark_dev_" 開頭且長度為 40
        And 儲存的 key 不含明文 secret 且 secret_prefix 為 secret 前 12 碼
        And 儲存的 key 能驗證該 secret
        And 稽核紀錄應記錄 "api_key" 的 "create"

    Scenario: 未知 scope 不能建立
        Given 租戶 "t1" 的 API key 建立命令 名稱 "看板" scopes "chat:send admin:all"
        When 執行建立 API key
        Then 建立應失敗並提示未知 scope

    Scenario: 撤銷 key 會遞增 token_version 並寫稽核
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send" token_version 1
        When 以租戶 "t1" 撤銷 API key "k1"
        Then key "k1" 應為已撤銷且 token_version 為 2
        And 稽核紀錄應記錄 "api_key" 的 "revoke"

    Scenario: 撤銷他租戶的 key 視為不存在
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send" token_version 1
        When 以租戶 "t2" 撤銷 API key "k1"
        Then 撤銷應失敗為找不到

    # --- 換票 ---

    Scenario: 正確的 client_id + secret 換得 api_access 票
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send chat:stream" token_version 1
        When 以 key "k1" 的正確 secret 換票 scope "chat:send"
        Then 換票成功且票的 type 為 "api_access" tenant_id "t1" scopes "chat:send" ver 1
        And key "k1" 的 last_used_at 應被更新

    Scenario: 未指定 scope 取得 key 全部 scopes
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send chat:stream" token_version 1
        When 以 key "k1" 的正確 secret 換票 scope "-"
        Then 換票成功且回應 scope 為 "chat:send chat:stream"

    Scenario: 要求超出 key 範圍的 scope 回 invalid_scope
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send" token_version 1
        When 以 key "k1" 的正確 secret 換票 scope "chat:send kb:write"
        Then 換票應失敗為 invalid_scope

    Scenario Outline: 不存在 / secret 錯 / 已撤銷 / 已過期 一律 invalid_client
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send" token_version 1
        And key "k1" 狀態為 "<state>"
        When 以 key "<client_id>" 的 "<secret>" secret 換票 scope "-"
        Then 換票應失敗為 invalid_client

        Examples:
            | state   | client_id | secret  |
            | active  | nope      | correct |
            | active  | k1        | wrong   |
            | revoked | k1        | correct |
            | expired | k1        | correct |

    # --- 每請求驗票 ---

    Scenario: ver 不符（已撤銷或輪替）的票被拒
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send" token_version 2
        When 驗證 client "k1" ver 1 的 api_access 票
        Then 驗票應失敗為 invalid_client

    Scenario: ver 相符的票解析成 principal
        Given 租戶 "t1" 已有 API key "k1" scopes "chat:send" token_version 2
        When 驗證 client "k1" ver 2 的 api_access 票
        Then 驗票成功且 principal 的 tenant_id 為 "t1"
