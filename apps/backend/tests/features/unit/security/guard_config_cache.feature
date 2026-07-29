Feature: Guard 設定快取 (Guard Rules Config Cache)
    身為系統維運者
    我想要快取 Guard 規則設定
    以便每則 LINE 訊息不用重複查 DB（現況 check_input + check_output 各查一次）

    Scenario: TTL 內重複讀取只查一次 DB
        Given Guard 設定存在於 DB
        When 我連續讀取 Guard 設定兩次
        Then DB 只應被查詢一次
        And 兩次讀取結果應相同

    Scenario: 設定不存在時也快取 None 結果
        Given DB 中沒有 Guard 設定
        When 我連續讀取 Guard 設定兩次
        Then DB 只應被查詢一次
        And 讀取結果應為 None

    Scenario: 儲存設定後快取失效
        Given Guard 設定存在於 DB 且已被快取
        When 我儲存新的 Guard 設定後再次讀取
        Then 儲存應委派內層 repository
        And 再次讀取應重新查詢 DB
