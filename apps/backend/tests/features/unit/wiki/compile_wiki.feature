Feature: 編譯 Wiki 知識圖譜
  作為系統管理員，我要能觸發 Bot 關聯知識庫的 Wiki 編譯，
  將所有文件透過 LLM 擷取為結構化知識圖譜，供未來 Wiki 模式查詢使用

  Background:
    Given 租戶 "t-001" 存在
    And 該租戶已有知識庫 "kb-001"

  Scenario: 成功編譯包含兩份文件的知識庫
    Given Bot "bot-001" 綁定 "kb-001"
    And 知識庫 "kb-001" 內有 2 份客服文件
    When 觸發 Bot "bot-001" 的 Wiki 編譯
    Then 應建立一筆 WikiGraph 紀錄
    And WikiGraph 狀態應為 "ready"
    And WikiGraph 應包含至少 1 個節點

  Scenario: 編譯空知識庫應產生空 Wiki 但仍為 ready
    Given Bot "bot-002" 綁定 "kb-001"
    And 知識庫 "kb-001" 內無任何文件
    When 觸發 Bot "bot-002" 的 Wiki 編譯
    Then 應建立一筆 WikiGraph 紀錄
    And WikiGraph 狀態應為 "ready"
    And WikiGraph 應包含 0 個節點

  Scenario: Bot 未綁定知識庫時應拒絕編譯
    Given Bot "bot-003" 未綁定任何知識庫
    When 嘗試觸發 Bot "bot-003" 的 Wiki 編譯
    Then 應回傳「未綁定知識庫」錯誤

  Scenario: 既有 Wiki 重新編譯應覆蓋先前內容
    Given Bot "bot-004" 綁定 "kb-001" 且已有舊的 WikiGraph
    And 知識庫 "kb-001" 內有 1 份客服文件
    When 觸發 Bot "bot-004" 的 Wiki 編譯
    Then WikiGraph 的 updated_at 應被更新
    And WikiGraph 狀態應為 "ready"
