Feature: 異常分數與分級 (Abuse Score & Tiered Response)
    身為對外 AI 客服的維運者
    我想要重複注入與自動化連打會被短暫、分級、可解釋地降權，但不鎖真人
    以便紅隊複測時系統有反應，而正常客人最多只被降速

    Background:
        Given 記憶體版異常分數儲存與預設政策

    Scenario: 單次注入只到 L1 保守模式
        When 訪客 "v1" 一回合 Guard 命中
        Then 訪客 "v1" 的等級為 1
        And 訪客 "v1" 的決定為保守模式

    Scenario: 5 分鐘內 3 次注入升到 L2 並帶 retry_after
        When 訪客 "v1" 連續 3 回合 Guard 命中
        Then 訪客 "v1" 的等級為 2
        And 訪客 "v1" 的決定為固定文案 retry_after 300
        And 稽核應記錄 "abuse_control" 的 "escalate" 到等級 2

    Scenario: 連打達 L3 後進入冷卻
        When 訪客 "v1" 連續 3 回合 Guard 命中
        And 訪客 "v1" 一分鐘內送出 25 句正常訊息
        Then 訪客 "v1" 的等級為 3
        And 訪客 "v1" 的決定為拒絕

    Scenario: 等級鎖 TTL 到期自動回復，分數線性衰減
        When 訪客 "v1" 連續 3 回合 Guard 命中
        And 時間經過 20 分鐘
        Then 訪客 "v1" 的等級為 0
        And 訪客 "v1" 的分數低於 1

    Scenario: 連續無法分流從第 3 句起每句計 1 分
        When 訪客 "v1" 連續 4 回合無法分流
        Then 訪客 "v1" 的分數為 2
        When 訪客 "v1" 一回合正常分流
        And 訪客 "v1" 連續 2 回合無法分流
        Then 訪客 "v1" 的分數低於 3

    Scenario: 儲存失效時放行並記錄
        Given 異常分數儲存失效
        When 訪客 "v1" 一回合 Guard 命中
        Then 訪客 "v1" 的等級為 0
        And 訪客 "v1" 的決定為放行

    Scenario: 監控模式只記分不動作
        Given 政策模式為 "monitor"
        When 訪客 "v1" 連續 3 回合 Guard 命中
        Then 訪客 "v1" 的等級為 2
        And 訪客 "v1" 的決定為放行

    Scenario Outline: 各主體有最高等級上限
        When 主體 "<kind>" "s1" 連續 6 回合 Guard 命中
        Then 主體 "<kind>" "s1" 的等級為 <max>

        Examples:
            | kind      | max |
            | visitor   | 3   |
            | line_user | 3   |
            | user      | 2   |
            | client    | 2   |

    Scenario: 手動解除清空分數與等級並寫稽核
        When 訪客 "v1" 連續 3 回合 Guard 命中
        And 管理員 "admin-1" 解除訪客 "v1"
        Then 訪客 "v1" 的等級為 0
        And 稽核應記錄 "abuse_control" 的 "release"

    Scenario: 保守模式關掉工具、top-k 減半、加婉拒指令
        When 對 bot 設定套用保守模式
        Then bot 設定的 enabled_tools 為空、rag_top_k 由 6 變 3、system_prompt 含保守指令
