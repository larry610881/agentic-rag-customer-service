Feature: Wiki 知識查詢（Strategy Pattern）
  作為客服 Bot，我要能用 wiki 模式查詢知識庫，
  依照設定的 navigation strategy 從 WikiGraph 找出相關節點回答使用者問題

  Background:
    Given 租戶 "t-001" 存在
    And 該租戶有 Bot "bot-001" 知識模式為 "wiki"

  Scenario: 以 keyword_bfs 策略查詢命中節點
    Given Bot "bot-001" 已編譯完成的 WikiGraph 包含「退貨政策」「退款流程」節點
    And navigation strategy 設定為 "keyword_bfs"
    And LLM 關鍵字抽取會回傳 "退貨"
    When 使用者查詢 "我要怎麼退貨？"
    Then 查詢應成功
    And 回傳 sources 應包含「退貨政策」節點
    And 回傳 sources 應遵守 RAG tool schema

  Scenario: Bot wiki graph 未編譯時回可讀錯誤訊息
    Given Bot "bot-001" 沒有編譯過的 WikiGraph
    When 使用者查詢 "任何問題"
    Then 查詢應成功
    And 回傳 context 應包含「尚未編譯」提示
    And 回傳 sources 應為空陣列

  Scenario: Bot wiki graph status 為 compiling 時回可讀錯誤訊息
    Given Bot "bot-001" 的 WikiGraph status 為 "compiling"
    When 使用者查詢 "任何問題"
    Then 查詢應成功
    And 回傳 context 應包含「編譯中」提示

  Scenario: LLM 關鍵字抽取失敗時降級為字串 unigram 匹配
    Given Bot "bot-001" 已編譯完成的 WikiGraph 包含「退貨政策」節點
    And navigation strategy 設定為 "keyword_bfs"
    And LLM 關鍵字抽取會拋出例外
    When 使用者查詢 "退貨怎麼辦"
    Then 查詢應成功
    And 回傳 sources 應至少包含 1 個節點
