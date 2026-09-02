Feature: Log 保留政策排程 (Log Retention Cron)
    身為維運
    我想要 log_retention_policies 由 worker 每小時檢查並在 cleanup_hour 執行
    以便 request_logs 不再無限成長

    Scenario: worker cron 清單含 log_retention_cleanup
        When 讀取 worker 的 cron 清單
        Then cron 清單應包含 "log_retention_cleanup_task"

    Scenario Outline: 依政策判斷是否該執行
        Given 保留政策 enabled=<enabled> cleanup_hour=<hour> interval=<interval> 上次執行=<last>
        When 於 UTC <now_hour> 點判斷是否執行
        Then 判斷結果應為 <should_run>

        Examples:
            | enabled | hour | interval | last    | now_hour | should_run |
            | true    | 3    | 24       | none    | 3        | true       |
            | true    | 3    | 24       | none    | 4        | false      |
            | true    | 3    | 12       | none    | 15       | true       |
            | true    | 3    | 24       | 30min   | 3        | false      |
            | false   | 3    | 24       | none    | 3        | false      |

    Scenario: 到點時執行清理
        Given 保留政策 enabled=true cleanup_hour=3 interval=24 上次執行=none
        When worker 於 UTC 3 點執行 log_retention_cleanup_task
        Then 應呼叫 ExecuteLogCleanupUseCase

    Scenario: 未到點不執行清理
        Given 保留政策 enabled=true cleanup_hour=3 interval=24 上次執行=none
        When worker 於 UTC 10 點執行 log_retention_cleanup_task
        Then 不應呼叫 ExecuteLogCleanupUseCase
