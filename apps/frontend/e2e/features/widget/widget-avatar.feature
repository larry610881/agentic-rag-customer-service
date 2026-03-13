Feature: Widget Avatar 渲染

  @skip
  Scenario: Widget 載入 Live2D Avatar
    Given Bot 設定 avatar_type 為 "live2d" 且有有效的 model URL
    When Widget 初始化完成
    Then Widget 聊天面板上方應顯示 canvas 渲染區域

  @skip
  Scenario: Widget 載入 VRM Avatar
    Given Bot 設定 avatar_type 為 "vrm" 且有有效的 model URL
    When Widget 初始化完成
    Then Widget 聊天面板上方應顯示 WebGL canvas

  @skip
  Scenario: 無 Avatar 的 Widget
    Given Bot 設定 avatar_type 為 "none"
    When Widget 初始化完成
    Then Widget 不應包含 Avatar 區域
