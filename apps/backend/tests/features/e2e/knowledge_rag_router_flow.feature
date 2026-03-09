Feature: 知識庫 RAG Router 完整旅程
  身為租戶管理員，我建立知識庫、上傳文件、配置 Bot，
  然後透過 Router Agent 發送對話並取得 RAG 回答。

  Scenario: 完整 RAG 對話旅程（Router 模式）
    Given 已建立租戶 "E2E Corp" 並取得 token
    And 已建立知識庫 "退貨FAQ"
    And 已上傳文件 "退貨政策.txt" 到知識庫
    And 已建立 Bot "客服小幫手" 綁定知識庫 agent_mode 為 "router"
    When 我透過 Bot 發送對話 "退貨政策是什麼？"
    Then 回應狀態碼為 200
    And 回答應包含知識庫相關內容
    And conversation_id 應非空

  Scenario: 無知識庫文件時的回答
    Given 已建立租戶 "Empty Corp" 並取得 token
    And 已建立知識庫 "空的FAQ"
    And 已建立 Bot "空Bot" 綁定知識庫 agent_mode 為 "router"
    When 我透過 Bot 發送對話 "退貨政策是什麼？"
    Then 回應狀態碼為 200
    And 回答應包含無資料提示

  Scenario: 對話歷史連續性
    Given 已建立租戶 "History Corp" 並取得 token
    And 已建立知識庫 "退貨FAQ"
    And 已上傳文件 "退貨政策.txt" 到知識庫
    And 已建立 Bot "客服小幫手" 綁定知識庫 agent_mode 為 "router"
    When 我透過 Bot 發送對話 "退貨政策是什麼？"
    And 我使用同一 conversation_id 發送對話 "那換貨呢？"
    Then 兩次回應的 conversation_id 應相同
    And 第二次回應應正常
