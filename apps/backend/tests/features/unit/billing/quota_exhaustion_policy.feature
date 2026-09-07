Feature: 額度用盡策略 (Issue #74 自動展延 / 用完即擋)
    身為系統管理員
    我要每個方案設定額度用盡後是自動展延還是用完即擋，並決定租戶能否自改
    以便三通路與背景任務都用同一份預檢，被擋時回固定文案

    # --- domain: decide ---

    Scenario: 自動展延策略永遠放行
        When 以策略 "auto_topup" 剩餘 -50 基礎額度 1000 寬限 0 判斷
        Then 判斷結果為放行

    Scenario: 用完即擋策略在剩餘額度大於 0 時放行
        When 以策略 "block" 剩餘 10 基礎額度 1000 寬限 0 判斷
        Then 判斷結果為放行

    Scenario: 用完即擋策略在額度用盡時攔阻
        When 以策略 "block" 剩餘 0 基礎額度 1000 寬限 0 判斷
        Then 判斷結果為攔阻

    Scenario: 寬限百分比內放行並標記已套用寬限
        When 以策略 "block" 剩餘 -50 基礎額度 1000 寬限 10 判斷
        Then 判斷結果為放行
        And 判斷結果已套用寬限

    Scenario: 超過寬限百分比攔阻
        When 以策略 "block" 剩餘 -100 基礎額度 1000 寬限 10 判斷
        Then 判斷結果為攔阻

    # --- 被擋文案解析 ---

    Scenario Outline: 被擋文案依租戶覆寫、方案、平台預設順序解析
        When 以租戶覆寫 "<tenant_override>" 方案文案 "<plan_message>" 解析被擋文案
        Then 解析出的被擋文案為 "<expected>"

        Examples:
            | tenant_override | plan_message | expected     |
            | 租戶自訂         | 方案自訂      | 租戶自訂      |
            |                 | 方案自訂      | 方案自訂      |
            |                 |              | 平台預設文案   |

    # --- application: 自動展延 ---

    Scenario: 自動展延策略在額度用盡時加購
        Given 方案 "pro" 策略 "auto_topup" 加購包 1000 tokens 月上限 0
        And 租戶 "t1" 本月額度已用盡
        When 租戶 "t1" 記錄一筆用量
        Then 應執行 1 次自動加購

    Scenario: 自動展延達月上限後停止加購
        Given 方案 "pro" 策略 "auto_topup" 加購包 1000 tokens 月上限 2
        And 租戶 "t1" 本月已自動加購 2 次
        When 對租戶 "t1" 執行自動展延
        Then 不應寫入加購紀錄

    Scenario: 用完即擋策略不自動加購
        Given 方案 "pro" 策略 "block" 加購包 1000 tokens 月上限 0
        And 租戶 "t1" 本月額度已用盡
        When 租戶 "t1" 記錄一筆用量
        Then 應執行 0 次自動加購

    Scenario: 租戶覆寫策略優先於方案預設
        Given 方案 "pro" 策略 "auto_topup" 加購包 1000 tokens 月上限 0
        And 租戶 "t1" 覆寫策略為 "block"
        And 租戶 "t1" 本月額度已用盡
        When 租戶 "t1" 記錄一筆用量
        Then 應執行 0 次自動加購

    # --- application: 三通路預檢 ---

    Scenario Outline: 用完即擋時三通路回固定文案
        Given 租戶 "t1" 的預檢結果為攔阻，文案 "本月額度已用完"
        When 通路 "<channel>" 的使用者發送訊息
        Then 通路 "<channel>" 收到固定文案 "本月額度已用完"
        And 不應呼叫 Agent

        Examples:
            | channel |
            | web     |
            | widget  |
            | line    |

    Scenario: 額度充足時三通路正常進入 Agent
        Given 租戶 "t1" 的預檢結果為放行
        When 通路 "web" 的使用者發送訊息
        Then 應呼叫 Agent

    Scenario: 背景文件處理在額度用盡時不啟動並標記狀態
        Given 租戶 "t1" 的預檢結果為攔阻，文案 "本月額度已用完"
        When 處理租戶 "t1" 的文件 "doc-1"
        Then 文件 "doc-1" 狀態為 "quota_exhausted"
        And 不應解析文件內容

    Scenario: 評估跑批入口在額度用盡時拋出相同錯誤
        Given 租戶 "t1" 的預檢結果為攔阻，文案 "本月額度已用完"
        When 確認租戶 "t1" 類別 "eval_gate" 可用
        Then 應拋出 QuotaExhaustedError 且訊息為 "本月額度已用完"

    # --- application: 預檢快取與 fail-open ---

    Scenario: 預檢結果快取 30 秒
        Given 租戶 "t1" 的配額為策略 "block" 剩餘 100
        When 連續預檢租戶 "t1" 類別 "chat_web" 2 次
        Then 配額只計算 1 次
        And 預檢快取以 30 秒寫入 "quota:pre:t1"

    Scenario: 寫入用量後預檢快取失效
        Given 租戶 "t1" 的配額為策略 "block" 剩餘 100
        When 租戶 "t1" 記錄一筆用量
        Then 預檢快取 "quota:pre:t1" 應被清除

    Scenario: 配額查詢失敗時預檢放行
        Given 租戶 "t1" 的配額查詢會失敗
        When 預檢租戶 "t1" 類別 "chat_web"
        Then 預檢結果為放行且原因為 "fail_open"

    Scenario: 不計入額度的類別不受攔阻
        Given 租戶 "t1" 的配額為策略 "block" 剩餘 0 且只計入 "chat_web"
        When 預檢租戶 "t1" 類別 "embedding"
        Then 預檢結果為放行且原因為 "not_billable"

    # --- application: 租戶自改策略 ---

    Scenario: 方案不允許時租戶管理員不可改策略
        Given 方案 "pro" 不允許租戶自改策略
        When 租戶管理員將租戶 "t1" 策略改為 "block"
        Then 應拒絕存取

    Scenario: 方案允許時租戶管理員可改策略並寫稽核
        Given 方案 "pro" 允許租戶自改策略
        When 租戶管理員將租戶 "t1" 策略改為 "block"
        Then 租戶 "t1" 的策略覆寫為 "block"
        And 應寫入 "tenant_billing" 稽核紀錄

    Scenario: 系統管理員不受方案限制可改策略
        Given 方案 "pro" 不允許租戶自改策略
        When 系統管理員將租戶 "t1" 策略改為 "block"
        Then 租戶 "t1" 的策略覆寫為 "block"
