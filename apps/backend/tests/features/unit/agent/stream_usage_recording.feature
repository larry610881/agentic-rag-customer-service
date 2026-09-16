Feature: 串流記帳不因客戶端斷線遺失（Issue #96，M12）
  記帳在 use case 內完成，三通路共用；串流收尾（存對話 → 記帳 → 存 trace）
  受 shielded cancel scope 保護，客戶端斷線只會延後到收尾完成後才生效。

  Scenario: 串流正常完成時在 use case 內記帳一次
    Given 一個會串出 token 與 usage 的 kb bot
    When 以 web 串流送出訊息並完整讀完
    Then record_usage 被呼叫 1 次
    And 記帳帶有 message_id、request_type "chat_web" 與 run_id "run-1"
    And 對話已儲存
    And 事件序列以 done 結尾

  Scenario: 客戶端在收尾階段斷線仍完成記帳與存檔
    Given 一個會串出 token 與 usage 的 kb bot
    And 儲存對話需要 0.2 秒
    When 以 web 串流送出訊息並在儲存對話進行中斷線
    Then record_usage 被呼叫 1 次
    And 對話已儲存
    And 沒有其他例外

  Scenario: 客戶端在生成中斷線時不記帳、不存檔、不拋其他例外
    Given 一個會串出 token 與 usage 的 kb bot
    When 以 web 串流送出訊息並在第一個 token 後斷線
    Then record_usage 被呼叫 0 次
    And 對話未儲存
    And 只發生取消，沒有其他例外

  Scenario: 非串流回覆也在 use case 內記帳一次
    Given 一個會串出 token 與 usage 的 kb bot
    When 以 web 非串流送出訊息
    Then record_usage 被呼叫 1 次
    And 記帳帶有 message_id、request_type "chat_web" 與 run_id "run-1"

  Scenario: 未指定 request_type 時依 identity_source 決定分類
    Given 一個會串出 token 與 usage 的 kb bot
    When 以 identity_source "widget" 且未指定 request_type 串流送出訊息並完整讀完
    Then 記帳的 request_type 為 "chat_widget"

  Scenario: 記帳失敗不影響串流完成
    Given 一個會串出 token 與 usage 的 kb bot
    And record_usage 會拋例外
    When 以 web 串流送出訊息並完整讀完
    Then 事件序列以 done 結尾
