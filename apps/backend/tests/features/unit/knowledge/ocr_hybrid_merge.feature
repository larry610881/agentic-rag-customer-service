Feature: 切片 OCR 混合整頁補漏（Issue #82）
  切片 OCR（2x3 / 3x2）提升字形辨識率，但「半個商品直接省略」規則加 80px overlap
  仍會漏掉橫跨切片邊界的大區塊（DM p13 艾瑪絲贈品整塊消失）。
  混合模式：切片之外再跑一次整頁 OCR（同 prompt 家族、不帶切片前綴、可降解析度），
  以正規化商品名合併：共用 block 保留切片版、整頁獨有的 block 補進來、
  「不詳」的頁面 markers 由整頁補上。輸出格式不變，splitter 不需改動。
  以 OCR_HYBRID_FULL_PAGE 環境變數控制，設定切片格線時預設開啟。

  Background:
    Given 一個記錄每次呼叫 prompt 的假 OCR 引擎

  Scenario: 設定切片格線時預設同時執行整頁 OCR 並合併
    Given 知識庫 ocr_mode 為 "catalog" 且 ocr_slice_grid 為 "2x3"
    When 對一張頁面影像執行 OCR
    Then OCR 引擎應被呼叫 7 次
    And 其中 6 次 prompt 帶切片補充規則、1 次不帶
    And OCR 結果應包含商品 "艾瑪絲 森系列洗髮精系列" 恰好 1 次
    And OCR 結果應包含商品 "木之薈樟腦油" 恰好 1 次

  Scenario: OCR_HYBRID_FULL_PAGE 關閉時僅執行切片 OCR
    Given 環境設定 OCR_HYBRID_FULL_PAGE 為 false
    And 知識庫 ocr_mode 為 "catalog" 且 ocr_slice_grid 為 "2x3"
    When 對一張頁面影像執行 OCR
    Then OCR 引擎應被呼叫 6 次
    And 其中 6 次 prompt 帶切片補充規則、0 次不帶
    And OCR 結果不應包含商品 "艾瑪絲 森系列洗髮精系列"

  Scenario: 未設定切片格線時維持單次整頁 OCR
    Given 知識庫 ocr_mode 為 "catalog" 且 ocr_slice_grid 為 ""
    When 對一張頁面影像執行 OCR
    Then OCR 引擎應被呼叫 1 次
    And 其中 0 次 prompt 帶切片補充規則、1 次不帶
    And OCR 結果應包含商品 "艾瑪絲 森系列洗髮精系列" 恰好 1 次

  Scenario: auto 模式切片時整頁補漏使用偵測類型對應的 prompt
    Given 知識庫 ocr_mode 為 "auto" 且 ocr_slice_grid 為 "2x3"
    When 對一張頁面影像執行 OCR
    Then 頁面分類應被呼叫 1 次
    And OCR 引擎應被呼叫 7 次
    And 其中 6 次 prompt 帶切片補充規則、1 次不帶
    And 不帶切片補充規則的 prompt 應為 catalog prompt

  Scenario: general 模式無結構化 block 時不執行整頁補漏
    Given 知識庫 ocr_mode 為 "general" 且 ocr_slice_grid 為 "2x3"
    When 對一張頁面影像執行 OCR
    Then OCR 引擎應被呼叫 6 次
    And 其中 6 次 prompt 帶切片補充規則、0 次不帶
