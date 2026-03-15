Feature: 身份解析
  作為系統，需要將訪客的外部 ID 解析為持久的 VisitorProfile

  Scenario: 新訪客首次造訪建立 Profile
    Given 租戶 "t-001" 沒有任何訪客資料
    When Widget 訪客 "visitor-abc" 發送訊息
    Then 應建立新的 VisitorProfile
    And 應建立 VisitorIdentity source 為 "widget"

  Scenario: 同一訪客再次造訪找到既有 Profile
    Given 租戶 "t-001" 已有 Widget 訪客 "visitor-abc" 的 Profile
    When Widget 訪客 "visitor-abc" 發送訊息
    Then 應回傳既有的 profile_id
    And 不應建立新的 Profile

  Scenario: 同一 external_id 不同 source 建立獨立 Profile
    Given 租戶 "t-001" 已有 Widget 訪客 "user-123" 的 Profile
    When LINE 用戶 "user-123" 發送訊息
    Then 應建立新的 VisitorProfile
    And 兩個 Profile 的 id 不同

  Scenario: 不同租戶相同 external_id 各自獨立
    Given 租戶 "t-001" 已有 Widget 訪客 "visitor-abc" 的 Profile
    When 租戶 "t-002" 的 Widget 訪客 "visitor-abc" 發送訊息
    Then 應建立新的 VisitorProfile
    And 兩個 Profile 的 tenant_id 不同
