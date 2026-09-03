Feature: Worker 端點租戶隔離 (Worker Tenant Isolation)
    身為租戶管理員
    我只能讀寫自己租戶 bot 底下的 worker
    以便其他租戶猜到 bot_id / worker_id 也碰不到我的設定

    Scenario: 無憑證列出 worker 回傳 401
        Given 已啟動的 worker 測試應用
        When 無憑證列出 bot "bot-a" 的 worker
        Then worker 回應狀態碼為 401

    Scenario Outline: 依 bot 歸屬決定 worker 端點是否可用
        Given 已啟動的 worker 測試應用
        And 以角色 "<role>" 租戶 "<tenant>" 的 worker 憑證
        And bot "bot-a" 屬於租戶 "t1"
        When 請求 worker 端點 "<method>" "<path>"
        Then worker 回應狀態碼為 <status>

        Examples:
            | role         | tenant | method | path                          | status |
            | user         | t1     | GET    | /api/v1/bots/bot-a/workers    | 200    |
            | user         | t2     | GET    | /api/v1/bots/bot-a/workers    | 404    |
            | user         | t2     | POST   | /api/v1/bots/bot-a/workers    | 404    |
            | user         | t2     | PUT    | /api/v1/bots/bot-a/workers/w1 | 404    |
            | user         | t2     | DELETE | /api/v1/bots/bot-a/workers/w1 | 404    |
            | system_admin | SYSTEM | GET    | /api/v1/bots/bot-a/workers    | 200    |

    Scenario: 更新其他 bot 的 worker 回傳 404
        Given 已啟動的 worker 測試應用
        And 以角色 "user" 租戶 "t1" 的 worker 憑證
        And bot "bot-a" 屬於租戶 "t1"
        And worker "w1" 屬於 bot "bot-b"
        When 請求 worker 端點 "PUT" "/api/v1/bots/bot-a/workers/w1"
        Then worker 回應狀態碼為 404

    Scenario: 刪除其他 bot 的 worker 回傳 404 且不執行刪除
        Given 已啟動的 worker 測試應用
        And 以角色 "user" 租戶 "t1" 的 worker 憑證
        And bot "bot-a" 屬於租戶 "t1"
        And worker "w1" 屬於 bot "bot-b"
        When 請求 worker 端點 "DELETE" "/api/v1/bots/bot-a/workers/w1"
        Then worker 回應狀態碼為 404
        And worker 儲存庫不應被刪除
