Feature: Bot Studio 試運轉 — identity_source 與 trace_id 整合
  租戶設定完 bot 後，Studio Tab 會以 identity_source="studio" 送 chat（stream），
  讓 trace 自然分流；並在 stream done 事件帶 trace_id，
  讓前端可以 fetch 完整 trace 渲染最終 DAG。

  Scenario: Stream chat 帶 identity_source studio 時 trace 應持久化 source studio
    Given 一般租戶已登入
    And 該租戶已建立一個 bot
    When 我送出 POST /api/v1/agent/chat/stream 帶 identity_source "studio"
    Then SSE done 事件應包含 trace_id 欄位
    And DB 中該 trace_id 對應的 trace.source 應為 "studio"

  Scenario: Stream chat 不帶 identity_source 時 trace.source 應預設為 web（向後相容）
    Given 一般租戶已登入
    And 該租戶已建立一個 bot
    When 我送出 POST /api/v1/agent/chat/stream 不帶 identity_source
    Then SSE done 事件應包含 trace_id 欄位
    And DB 中該 trace_id 對應的 trace.source 應為 "web"
