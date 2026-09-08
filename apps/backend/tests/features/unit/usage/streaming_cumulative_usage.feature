Feature: 串流累計 usage 不可逐 chunk 相加（Issue #90）
  作為平台
  我希望走 OpenAI 相容端點串流時，記帳用的 usage 是供應商回報的最終值
  以便 Gemini 這類「每個 chunk 都帶累計 usage」的供應商不會被記成數倍成本

  Scenario: Gemini 形狀（每個 chunk 都帶累計 usage）合併後應等於最後一筆
    Given 一個 base_url 指向 googleapis 的相容聊天模型
    And 串流依序回傳三個 chunk，usage 分別為 input 1000/output 10、input 1000/output 20、input 1000/output 30
    When 我把串流的 chunk 全部相加成最終訊息
    Then 最終訊息的 usage 應為 input 1000、output 30

  Scenario: OpenAI 形狀（只有最後一個 chunk 帶 usage）行為不變
    Given 一個 base_url 指向 googleapis 的相容聊天模型
    And 串流依序回傳三個 chunk，只有最後一個帶 usage input 1000/output 30
    When 我把串流的 chunk 全部相加成最終訊息
    Then 最終訊息的 usage 應為 input 1000、output 30

  Scenario: 串流的文字內容不受影響
    Given 一個 base_url 指向 googleapis 的相容聊天模型
    And 串流依序回傳三個 chunk，usage 分別為 input 1000/output 10、input 1000/output 20、input 1000/output 30
    When 我把串流的 chunk 全部相加成最終訊息
    Then 最終訊息的文字應為三個 chunk 的內容串接

  Scenario: 工廠只對 googleapis 端點換成保留最後 usage 的模型
    When 我用工廠建立 base_url 為 "https://generativelanguage.googleapis.com/v1beta/openai" 的模型
    Then 建出來的模型應為保留最後 usage 的類別
    When 我用工廠建立 base_url 為 "https://api.openai.com/v1" 的模型
    Then 建出來的模型應為一般 ChatOpenAI
