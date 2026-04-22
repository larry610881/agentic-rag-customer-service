Feature: 對話摘要列表與搜尋（獨立 admin 頁）
  作為系統管理員
  我希望以 tenant/bot filter 瀏覽對話摘要
  以便稽核對話品質與搜尋近似問題

  Scenario: Tenant admin 列自家對話摘要
    Given 租戶 "T001" 有 5 筆 conv_summaries（2 筆 bot="bot-A"、3 筆 bot="bot-B"）
    And 租戶 "T002" 有 3 筆 conv_summaries
    When 我以 tenant "T001" 的 tenant_admin 身分呼叫 list_conv_summaries(tenant_id="T001")
    Then 回傳應含 5 筆
    And 所有筆數的 tenant_id 應為 "T001"

  Scenario: Bot filter 只列該 bot 的摘要
    Given 租戶 "T001" 有 conv_summaries 跨 bot-A(2) + bot-B(3)
    When 我呼叫 list_conv_summaries(tenant_id="T001", bot_id="bot-A")
    Then 回傳應含 2 筆
    And 所有筆數的 bot_id 應為 "bot-A"

  Scenario: 跨租戶 bot_id 必驗（安全紅線）
    Given 租戶 "T001" 擁有 bot "bot-A"
    When 我以 tenant "T002" 身分呼叫 list_conv_summaries(tenant_id="T002", bot_id="bot-A")
    Then 應拋出 EntityNotFoundError（404 防枚舉）

  Scenario: Platform admin 禁止無 tenant filter 撈全集
    When 我以 platform_admin 身分呼叫 list_conv_summaries()（無 tenant_id）
    Then 應拋出 ValueError 訊息含 "tenant_id required"
