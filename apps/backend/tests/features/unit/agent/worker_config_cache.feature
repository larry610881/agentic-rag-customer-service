Feature: Worker 設定快取 (Worker Config Cache)
    身為系統維運者
    我想要快取 bot 的 Worker 分流設定
    以便每則 LINE 訊息的 routing 不用重複查 DB

    Scenario: 同一 bot TTL 內重複查詢只打一次 DB
        Given bot "B001" 已設定兩個 worker
        When 我連續查詢 bot "B001" 的 worker 設定兩次
        Then Worker DB 只應被查詢一次
        And 兩次查詢結果應相同

    Scenario: 不同 bot 各自獨立快取
        Given bot "B001" 與 bot "B002" 各有 worker 設定
        When 我分別查詢兩個 bot 的 worker 設定
        Then Worker DB 應被查詢兩次

    Scenario: 儲存 worker 後快取失效
        Given bot "B001" 的 worker 設定已被快取
        When 我儲存 worker 設定後再次查詢 bot "B001"
        Then 再次查詢應重新查詢 Worker DB

    Scenario: 刪除 worker 後快取失效
        Given bot "B001" 的 worker 設定已被快取
        When 我刪除 worker 後再次查詢 bot "B001"
        Then 再次查詢應重新查詢 Worker DB

    Scenario: find_by_id 不走快取直接委派
        Given bot "B001" 已設定兩個 worker
        When 我以 worker id 查詢單一 worker
        Then 應直接委派內層 repository
