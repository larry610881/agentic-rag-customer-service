Feature: Prompt 發布閘門端到端流程
  # Issue #54 — steps 待 dev 環境重建（seed 資料 + 後端運行）後實作。
  # 前置：make seed-data + scripts/seed_platform_gate_dataset.py 已跑、
  # 至少一個 bot 綁定含啟用案例的自訂題集。

  Scenario: 編輯 prompt 被靜態檢查擋下後修正並發布（gate off）
    Given 我以租戶管理員登入
    And 進入某個 gate_mode 為 off 的機器人設定頁
    When 我將系統提示詞改為含 "忽略以上指示" 的內容並儲存
    Then 應顯示靜態檢查失敗與違規明細
    When 我修正提示詞為合法內容並儲存
    Then 應顯示儲存成功
    And 版本與發布頁應出現新的已發布版本

  Scenario: 閘門 block 模式完整驗證流程
    Given 我以租戶管理員登入且租戶已開啟發布閘門
    And 機器人 gate_mode 為 block 並已綁定題集
    When 我修改系統提示詞並儲存
    Then 應提示需走版本 API 送驗
    When 我在版本頁對 draft 送驗
    Then 應先顯示成本預檢並確認
    And 驗證完成後顯示逐題報告
    When 驗證通過且我按發布
    Then 版本狀態應為已發布且標記線上

  Scenario: 對照測試 Playground 雙欄回應
    Given 我以租戶管理員登入並開啟某機器人的對照測試
    When 我輸入一句測試訊息送出
    Then 左右兩欄應各自出現回應
    And 介面應顯示 token 消耗提醒

  Scenario: 未綁題集時閘門無法啟用
    Given 我以租戶管理員登入
    And 進入未綁定題集的機器人設定頁
    When 我將 gate_mode 改為 block 並儲存
    Then 應顯示「須先設定問題集」錯誤
