Feature: Widget 身分階梯與通路補強 (Widget Identity Ladder, P7b)
    身為店家
    我要能用通用協定把自家會員 id 綁進 widget（identify），簽發端點有限速，LINE 群組洗版者被靜默
    以便攻擊者不能換身分重置分數，而正常會員的對話能被正確歸戶

    # --- identify 協定（domain）---

    Scenario: 宿主後端以租戶 secret 算出的 hash 可通過驗證
        Given 租戶 identity secret "s3cr3t"
        When 宿主為使用者 "member-42" 產生 10 分鐘後到期的簽章
        Then 驗證結果為通過

    Scenario Outline: 錯誤簽章、過期或超過 24 小時的 exp 都不通過
        Given 租戶 identity secret "s3cr3t"
        When 宿主為使用者 "member-42" 產生 <exp_offset> 秒後到期的簽章，並以 "<tamper>" 竄改
        Then 驗證結果為不通過

        Examples:
            | exp_offset | tamper  |
            | 600        | hash    |
            | 600        | user_id |
            | -1         | none    |
            | 90000      | none    |

    # --- identify 用例 ---

    Scenario: 驗證通過回 verified，失敗計 identify_fail 並依租戶設定決定是否強制
        Given 租戶 "t1" 已設定 identity secret，強制驗證 關閉
        When 訪客 "v1" 送出正確的 identify
        Then identify 結果 verified 為 true
        When 訪客 "v1" 送出錯誤的 identify
        Then identify 結果 verified 為 false 且 enforce 為 false
        And 訪客 "v1" 被記了 identify_fail

    Scenario: 租戶開強制驗證時失敗回 enforce
        Given 租戶 "t1" 已設定 identity secret，強制驗證 開啟
        When 訪客 "v1" 送出錯誤的 identify
        Then identify 結果 verified 為 false 且 enforce 為 true

    Scenario: 租戶未設定 secret 時視為未設定，不計分
        Given 租戶 "t1" 未設定 identity secret
        When 訪客 "v1" 送出錯誤的 identify
        Then identify 結果 reason 為 "not_configured"
        And 訪客 "v1" 沒有被記 identify_fail

    # --- identify 端點 ---

    Scenario: 持 widget 票 identify 成功後換到帶 end_user_id 的票
        Given 已啟動的 identify 測試應用，租戶 "t1" 強制驗證 關閉
        And 持有 bot "ab3Kx9" 的 widget 票
        When 持票送出正確的 identify "member-42"
        Then identify 端點回應 200 且 identified 為 true
        And 新票的 end_user_id 為 "member-42"

    Scenario: 強制驗證下錯誤簽章回 403 identity_required
        Given 已啟動的 identify 測試應用，租戶 "t1" 強制驗證 開啟
        And 持有 bot "ab3Kx9" 的 widget 票
        When 持票送出錯誤的 identify "member-42"
        Then identify 端點回應 403

    Scenario: 無票不能 identify
        Given 已啟動的 identify 測試應用，租戶 "t1" 強制驗證 關閉
        When 無票送出 identify "member-42"
        Then identify 端點回應 401

    # --- 簽發限速 ---

    Scenario Outline: widget 簽發端點自成限流群組
        When 解析路徑 "<path>" 的限流群組
        Then 限流群組為 "<group>"

        Examples:
            | path                              | group        |
            | /api/v1/widget/ab3Kx9/config      | widget_issue |
            | /api/v1/widget/ab3Kx9/chat/stream | widget       |
            | /api/v1/agent/chat                | rag          |

    # --- LINE 群組 ---

    Scenario: LINE 群組每分鐘總量超標時只對洗版者計節奏異常
        Given 接了異常控管的 LINE 群組 webhook use case，群組每分鐘上限 3
        When 群組 "G1" 的使用者 "U1" 連續送出 5 則訊息
        Then LINE 使用者 "U1" 的異常分數為 3
        And 群組 "G1" 的使用者 "U2" 送出 1 則訊息後分數為 0

    Scenario: 群組內 L2 以上的使用者一律靜默不回覆
        Given 接了異常控管的 LINE 群組 webhook use case，群組每分鐘上限 3
        And LINE 使用者 "U1" 已被鎖定在等級 2
        When 群組 "G1" 的使用者 "U1" 連續送出 1 則訊息
        Then LINE 沒有回覆任何訊息
