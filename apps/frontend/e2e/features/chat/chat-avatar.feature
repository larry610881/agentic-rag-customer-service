Feature: 後台 Chat Avatar 顯示

  Scenario: 選擇有 Live2D Avatar 的 Bot 時顯示 Avatar 面板
    Given 有一個 avatar_type 為 "live2d" 的 Bot
    When 我在 Chat 頁面選擇該 Bot
    Then 我應看到 Avatar 面板顯示在訊息列表上方

  Scenario: 選擇無 Avatar 的 Bot 時不顯示 Avatar 面板
    Given 有一個 avatar_type 為 "none" 的 Bot
    When 我在 Chat 頁面選擇該 Bot
    Then 我不應看到 Avatar 面板

  Scenario: 切換不同 Avatar 類型的 Bot
    Given 我正在與 avatar_type 為 "live2d" 的 Bot 對話
    When 我返回並選擇 avatar_type 為 "vrm" 的 Bot
    Then Avatar 面板應更新為 VRM 渲染器
    And 前一個 Live2D 渲染器應已被清除
