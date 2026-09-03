Feature: Widget 短效票與 Origin 白名單 (Widget Token)
    身為店家
    我嵌在自家網站的 widget 只能從白名單網域啟動，聊天 / 回饋 / 錯誤回報都要帶
    伺服器簽發的短效票，訪客身分也由伺服器簽發
    以便任何人拿到 short_code 也無法從別的網站或腳本直接打我的機器人

    Background:
        Given 已啟動的 widget 測試應用
        And bot "ab3Kx9" 允許的 Origin 為 "https://shop.example.com"

    Scenario Outline: 取得設定必須帶白名單內的 Origin
        When 以 Origin "<origin>" 取得 widget 設定
        Then widget 回應狀態碼為 <status>

        Examples:
            | origin                   | status |
            | https://shop.example.com | 200    |
            | https://evil.example.com | 403    |
            | -                        | 403    |

    Scenario: Origin 白名單為空一律拒絕
        Given bot "ab3Kx9" 的 Origin 白名單為空
        When 以 Origin "https://shop.example.com" 取得 widget 設定
        Then widget 回應狀態碼為 403

    Scenario: 設定回應附短效票與伺服器簽發的 visitor id
        When 以 Origin "https://shop.example.com" 取得 widget 設定
        Then widget 回應狀態碼為 200
        And 設定回應含 widget_token（type widget_access、綁 bot 與 Origin）與 expires_in 900
        And 設定回應的 visitor_id 帶有效簽章

    Scenario: 自報的 visitor id 若簽章有效則沿用，否則換發
        Given 已從設定取得 visitor_id
        When 以該 visitor_id 再取得一次 widget 設定
        Then 設定回應的 visitor_id 與先前相同
        When 以偽造的 visitor_id "someone-else.deadbeef" 取得 widget 設定
        Then 設定回應的 visitor_id 與先前不同

    Scenario Outline: 聊天 / 回饋 / 錯誤回報沒有票回 401
        When 無票請求 widget "<method>" "<path>"
        Then widget 回應狀態碼為 401

        Examples:
            | method | path                                   |
            | POST   | /api/v1/widget/ab3Kx9/chat/stream      |
            | POST   | /api/v1/widget/ab3Kx9/feedback         |
            | POST   | /api/v1/widget/ab3Kx9/error            |
            | GET    | /api/v1/widget/ab3Kx9/documents/d1/view |

    Scenario: 持票聊天：visitor 身分取自票而非 header
        Given 已從設定取得 widget 票
        When 持票以 Origin "https://shop.example.com" 與 header X-Visitor-Id "spoofed" 送出聊天
        Then widget 回應狀態碼為 200
        And 聊天命令的 visitor_id 等於票內 visitor_id 且 identity_source 為 "widget"

    Scenario: 票綁 Origin：換一個 Origin 用同一張票被拒
        Given 已從設定取得 widget 票
        When 持票以 Origin "https://evil.example.com" 送出聊天
        Then widget 回應狀態碼為 403

    Scenario: 票綁 bot：拿 A bot 的票打 B bot 被拒
        Given 已從設定取得 widget 票
        And 另一個 bot "zz9Qwe" 允許的 Origin 為 "https://shop.example.com"
        When 持票對 bot "zz9Qwe" 送出聊天
        Then widget 回應狀態碼為 401

    Scenario: 人類 access 票不能當 widget 票用
        When 以租戶使用者的 access 票送出聊天
        Then widget 回應狀態碼為 401

    Scenario: 文件檢視可用 query 參數帶票（新分頁開啟無法帶 header）
        Given 已從設定取得 widget 票
        When 以 query 參數帶票請求文件 "d1" 檢視
        Then widget 回應狀態碼為 200

    Scenario: 持票送出回饋
        Given 已從設定取得 widget 票
        When 持票以 Origin "https://shop.example.com" 送出回饋
        Then widget 回應狀態碼為 201
