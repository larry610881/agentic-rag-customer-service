Feature: Dataset Loader
  評估情境集的 YAML 載入與驗證

  Scenario: 載入有效的 dataset YAML
    Given 一個有效的 dataset YAML 內容
    When 我載入該 dataset
    Then 應成功解析並回傳 Dataset 物件
    And test_cases 數量應為預期值

  Scenario: 載入含 includes 的 dataset
    Given 一個含 includes 的 dataset YAML
    And 被 include 的檔案存在
    When 我載入該 dataset
    Then test_cases 應包含 include 檔案的 cases

  Scenario: Schema 驗證失敗 — 缺少必要欄位
    Given 一個缺少 metadata 的 dataset YAML
    When 我嘗試載入該 dataset
    Then 應拋出 DatasetValidationError

  Scenario: Schema 驗證失敗 — 未知的 assertion type
    Given 一個使用未知 assertion type 的 dataset YAML
    When 我嘗試載入該 dataset
    Then 應拋出 DatasetValidationError 並包含 assertion type 錯誤訊息

  Scenario: 重複的 case ID 檢測
    Given 一個含有重複 case ID 的 dataset YAML
    When 我嘗試載入該 dataset
    Then 應拋出 DatasetValidationError 並包含 duplicate 錯誤訊息

  Scenario: default_assertions 合併到每個 case
    Given 一個含 default_assertions 的 dataset YAML
    When 我載入該 dataset
    Then 每個 case 的 assertions 應包含 default_assertions
