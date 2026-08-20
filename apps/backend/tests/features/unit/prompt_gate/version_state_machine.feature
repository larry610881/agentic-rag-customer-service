Feature: Bot 設定版本狀態機
  draft → validating → pending_publish → published / rejected，
  is_current 唯一、append-only、非法轉移一律拒絕。

  Scenario: 建立 draft 版本（版號遞增 + changed_fields）
    Given Bot 已有線上版本 v1
    When 修改 base_prompt 建立新 draft
    Then 產生 version_no 為 2 的 draft 版本
    And draft 的 changed_fields 包含 base_prompt
    And 線上版本仍為 v1

  Scenario: 靜態檢查失敗不產生版本
    Given Bot 已有線上版本 v1
    When 以含 injection 句式的 base_prompt 建立 draft
    Then 建立被拒絕且錯誤含違規明細
    And 不產生任何新版本

  Scenario: 無變更不產生版本
    Given Bot 已有線上版本 v1
    When 以與現行完全相同的設定建立 draft
    Then 建立被拒絕且錯誤為 no_changes

  Scenario: gate 未啟用時發布 draft（verdict=skipped）
    Given Bot 已有線上版本 v1 且存在 draft v2
    When 發布 v2
    Then v2 狀態為 published 且 gate_verdict 為 skipped
    And v2 成為 is_current 且 v1 不再是 is_current
    And Bot 實體已套用 v2 快照

  Scenario: 發布已 published 的版本被拒絕
    Given Bot 已有線上版本 v1
    When 對 v1 再次發布
    Then 操作被拒絕（非法狀態轉移）

  Scenario: 放棄 draft
    Given Bot 已有線上版本 v1 且存在 draft v2
    When 放棄 v2
    Then v2 狀態為 rejected
    And 線上版本仍為 v1

  Scenario: 放棄已 published 的版本被拒絕
    Given Bot 已有線上版本 v1
    When 對 v1 執行放棄
    Then 操作被拒絕（非法狀態轉移）

  Scenario: 回朔到歷史 published 版本
    Given Bot 依序發布過 v1 與 v2
    When 回朔到 v1
    Then 產生 version_no 為 3 的新版本且 source 為 rollback
    And v3 直接 published 且免重驗
    And v3 的快照內容等於 v1 的快照
    And v3 成為 is_current

  Scenario: 回朔目標必須是 published 版本
    Given Bot 已有線上版本 v1 且存在 draft v2
    When 回朔到 v2
    Then 操作被拒絕（回朔目標非 published）

  Scenario: 跨租戶版本操作被拒絕
    Given Bot 已有線上版本 v1 且存在 draft v2
    When 以其他租戶身分發布 v2
    Then 操作被拒絕（找不到版本）
