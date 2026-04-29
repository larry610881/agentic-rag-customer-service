Feature: KB Studio 管理員介面 (Admin KB Studio)
  作為平台管理員
  我希望能夠透過 KB Studio 管理知識庫
  以便檢視 / 編輯文件 chunks / 配置 AI 模型

  Background:
    Given 使用者已登入為 "Demo Store"
    And 使用者在知識庫頁面
    When 使用者點擊知識庫 "商品資訊"
    Then 應顯示文件管理頁面

  Scenario: KB Studio 5 個 tab 都能切換顯示
    Given 使用者導航至該知識庫的 KB Studio
    Then 應顯示 5 個 tab "文件管理" "分類" "Retrieval Playground" "品質" "設定"
    And 預設選中的 tab 應為 "文件管理"

  Scenario: 設定 tab 顯示 inline 編輯表單
    Given 使用者導航至該知識庫的 KB Studio
    When 使用者切換到 "設定" tab
    Then 應顯示 KB 名稱輸入欄位
    And 應顯示 OCR 模式選擇器
    And 應顯示 OCR 解析模型選擇器
    And 應顯示上下文生成模型選擇器
    And 應顯示自動分類模型選擇器

  Scenario: 舊網址 ?tab=overview 自動跳到文件管理（向後相容）
    When 使用者開啟 KB Studio 並使用舊參數 "?tab=overview"
    Then 預設選中的 tab 應為 "文件管理"

  Scenario: 文件 tab 顯示 dropzone + page header 統計卡片
    Given 使用者導航至該知識庫的 KB Studio
    Then 應顯示上傳區域
    And 應顯示文件統計卡片 "文件數"
    And 應顯示文件統計卡片 "處理中"
    And 應顯示文件統計卡片 "失敗"

  # 完整 chunk-edit round-trip（修改 → 持久 → 還原）需 seed 真實文件 + chunks
  # 這個 scenario 驗證 drill-down dialog UI surface：dialog 標題含「編輯」(chunkEditable=true)
  Scenario: 點開有 chunks 的文件 dialog 顯示「分塊編輯」標題
    Given 使用者導航至該知識庫的 KB Studio
    When 使用者點擊任一已處理文件的「查看分塊」按鈕
    Then 應顯示分塊編輯對話框
    And 對話框標題應包含 "分塊編輯"
