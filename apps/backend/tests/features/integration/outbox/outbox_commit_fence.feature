Feature: Outbox 提交圍欄 — request 結束後事件必須已 commit
    Outbox 事件以 session.add 寫入、不自行 commit，靠同一個 request 共用 session
    的後續 atomic() 業務寫入一起提交（例如 DeleteDocumentUseCase）。
    若 session 語意與 production 不同（每個 repository 各拿一個 session），
    事件會在 request 結束時被靜默丟掉 — 這道圍欄從「全新連線」檢查事件是否真的已提交。

    Scenario: 刪除文件後 vector.delete 事件已 commit（全新連線看得到）
        Given 已登入為租戶 "Fence Corp" 並建立知識庫 "FenceKB"
        And 該知識庫已有一份文件
        When 我透過 HTTP 刪除該文件
        Then 回應狀態碼為 204
        And 全新連線應看得到該文件的 vector.delete outbox 事件
        And request 結束後測試資料庫不應殘留 idle in transaction 連線

    Scenario: 只 publish 不 commit 的 request — 圍欄必須判定為未提交
        Given 測試用端點只 publish outbox 事件而沒有任何 atomic 寫入
        When 我呼叫該測試用端點
        Then 回應狀態碼為 200
        And request 內的 session 看得到該事件
        And 全新連線不應看得到該事件
        And request 結束後測試資料庫不應殘留 idle in transaction 連線

    Scenario: 同一測試用端點改為 standalone publish — 圍欄判定為已提交
        Given 測試用端點以 standalone 模式 publish outbox 事件
        When 我呼叫該測試用端點
        Then 回應狀態碼為 200
        And request 內的 session 看得到該事件
        And 全新連線應看得到該事件
