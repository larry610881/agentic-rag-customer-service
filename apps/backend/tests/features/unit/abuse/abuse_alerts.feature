Feature: 異常控管告警與通知 (Abuse Alerts & Notifications)
    身為維運者
    我要 L3 升級、控管失效（fail-open）、429 突增與每日摘要都送到 Teams（Email 為輔）
    以便控管默默失效或被連打時有人知道，而通知內容不洩漏使用者原文與完整 id

    Scenario: 主體升到 L3 立即發告警且主體 id 遮罩
        Given 告警服務與記憶體儲存
        When 訪客 "visitor-abcdef-123456" 在通路 "widget" 升到等級 3，原因 "guard_hit"
        Then 應發出 1 則 "escalation" 事件
        And 事件的主體為 "visitor visi…56" 且不含完整 id
        And 事件的等級為 3 且 retry_after 大於 0

    Scenario: 升到 L2 不發升級告警，只計入突增
        Given 告警服務與記憶體儲存
        When 訪客 "v1" 在通路 "widget" 升到等級 2，原因 "guard_hit"
        Then 應發出 0 則 "escalation" 事件

    Scenario: 5 分鐘內 429 與降速達 20 次只發一則突增告警
        Given 告警服務與記憶體儲存
        When 租戶被限流 25 次
        Then 應發出 1 則 "surge" 事件

    Scenario: fail-open 必發告警並計數，同租戶 15 分鐘內只發一次
        Given 告警服務與記憶體儲存
        And 控管服務的分數儲存失效
        When 控管服務評估訪客 "v1" 兩次
        Then 應發出 1 則 "fail_open" 事件
        And 事件摘要含 "操作：evaluate"

    Scenario: Teams 以 Workflows webhook 送 Adaptive Card
        Given 設定了 webhook_url 的 Teams 渠道與攔截的 HTTP 傳輸
        When 送出 Teams 通知 主旨 "[Abuse L3] 主體進入冷卻" 內文 "等級：L3\n通路：widget\n後台：/admin/audit-logs"
        Then Teams 收到 type "message" 且附件 contentType 為 "application/vnd.microsoft.card.adaptive"
        And Adaptive Card 含 FactSet 事實 "等級" 為 "L3"

    Scenario: Teams 渠道未設定 webhook_url 時跳過不失敗
        Given 未設定 webhook_url 的 Teams 渠道與攔截的 HTTP 傳輸
        When 送出 Teams 通知 主旨 "x" 內文 "y"
        Then Teams 未收到任何請求

    Scenario: 分派器解密設定並隔離單一渠道失敗
        Given 分派器掛了會解密的加密服務、一個會丟例外的 email 發送器與一個 teams 發送器
        When 對加密設定的 email 渠道與 teams 渠道各送一則通知
        Then email 發送器收到的設定為明文 JSON
        And teams 發送器仍被呼叫

    Scenario: 告警只送 notify_abuse 的渠道且內文不含完整 id
        Given 兩個啟用渠道，其中一個 notify_abuse 關閉
        When 分派一則 escalation 告警（主體 "visitor-abcdef-123456"）
        Then 只有 notify_abuse 的渠道收到通知
        And 通知內文含 "visi…56" 且不含 "visitor-abcdef-123456"

    Scenario: 每日摘要彙整升級 / 解除次數與 Top 主體
        Given 過去 24 小時的稽核紀錄：L3 升級 2 次、L2 升級 3 次、解除 1 次、更早的 L3 升級 5 次
        When 彙整摘要
        Then 摘要含 "L2 3、L3 2" 與 "手動解除：1"
        And 摘要的 Top 主體不含完整 id
