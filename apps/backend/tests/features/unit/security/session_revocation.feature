Feature: 後台 session 撤銷端點行為 (Session Revocation Surface)
    身為後台使用者
    我改密碼後、或 refresh 票被人重放後，舊票在 API 層就被擋下
    以便竊取的票在到期前失去作用

    Scenario: 改密碼後舊 access 票立即 401
        Given 已啟動的 session 測試應用
        And 使用者 "u1" 租戶 "t1" 持有 ver 1 的 access 票
        When 撤銷儲存記錄 "u1" 最低 ver 為 2
        And 以該 access 票請求 GET /api/v1/bots
        Then session 回應狀態碼為 401

    Scenario: 未被撤銷的 access 票照常可用
        Given 已啟動的 session 測試應用
        And 使用者 "u1" 租戶 "t1" 持有 ver 1 的 access 票
        When 以該 access 票請求 GET /api/v1/bots
        Then session 回應狀態碼為 200

    Scenario: /auth/refresh 旋轉後重放舊票回 401 並撤銷整組
        Given 已啟動的 session 測試應用
        And 使用者 "u1" 租戶 "t1" 持有已登記的 refresh 票
        When 以該 refresh 票呼叫 /auth/refresh
        Then session 回應狀態碼為 200
        And 回應含新的 access 與 refresh 票
        When 以原本的 refresh 票再呼叫 /auth/refresh
        Then session 回應狀態碼為 401
        When 以新的 refresh 票呼叫 /auth/refresh
        Then session 回應狀態碼為 401

    Scenario: 拿 access 票當 refresh 用回 401
        Given 已啟動的 session 測試應用
        And 使用者 "u1" 租戶 "t1" 持有 ver 1 的 access 票
        When 以該 access 票當 refresh 呼叫 /auth/refresh
        Then session 回應狀態碼為 401
