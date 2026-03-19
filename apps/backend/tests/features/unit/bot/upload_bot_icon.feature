Feature: 上傳機器人 FAB 圖示
  作為管理員，我要為機器人上傳自訂 FAB 按鈕圖片

  Scenario: 成功上傳 PNG 圖片
    Given 租戶 "t-001" 的機器人 "bot-001" 存在
    When 上傳 PNG 圖片 "icon.png" 大小 100KB
    Then 上傳應成功
    And 機器人 fab_icon_url 應包含 "bot-001"

  Scenario: 上傳過大檔案被拒
    Given 租戶 "t-001" 的機器人 "bot-001" 存在
    When 上傳 PNG 圖片 "big.png" 大小 512KB
    Then 應拋出檔案過大錯誤

  Scenario: 上傳不支援格式被拒
    Given 租戶 "t-001" 的機器人 "bot-001" 存在
    When 上傳 GIF 圖片 "icon.gif"
    Then 應拋出格式不支援錯誤

  Scenario: 不同租戶不可上傳其他租戶的機器人圖示
    Given 租戶 "t-002" 已登入
    And 機器人 "bot-001" 屬於租戶 "t-001"
    When 上傳 PNG 圖片至機器人 "bot-001"
    Then 應拋出 EntityNotFoundError
