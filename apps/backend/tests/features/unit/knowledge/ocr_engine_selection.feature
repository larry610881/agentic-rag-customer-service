Feature: OCR 引擎多供應商選擇（Issue #78）
  OCR 引擎依 model spec（provider:model）動態選擇：
  KB.ocr_model → 租戶 default_ocr_model → 環境預設。
  anthropic 走 Claude Vision；google / openai / openrouter / litellm 走 OpenAI 相容視覺端點。
  用量（input / output tokens）由每次呼叫的結果帶回，不依賴共用累計計數器，
  記帳的 model 欄位為實際 spec。

  Background:
    Given 環境預設 OCR 模型為 "anthropic:claude-sonnet-4-6"

  # ── 引擎選擇（KB → 租戶 → env）──

  Scenario: KB 指定 google 模型時走 OpenAI 相容引擎並使用 Gemini 端點
    Given 知識庫 ocr_model 為 "google:gemini-3.7-flash"
    And 租戶 default_ocr_model 為 "anthropic:claude-haiku-4-5"
    When 解析 OCR 引擎
    Then 應選用 OpenAI 相容視覺引擎
    And 引擎 base_url 應為 "https://generativelanguage.googleapis.com/v1beta/openai"
    And 引擎 model spec 應為 "google:gemini-3.7-flash"

  Scenario: KB 未設定時採用租戶預設的 anthropic 模型
    Given 知識庫 ocr_model 為 ""
    And 租戶 default_ocr_model 為 "anthropic:claude-haiku-4-5"
    When 解析 OCR 引擎
    Then 應選用 Claude Vision 引擎
    And 引擎 model spec 應為 "anthropic:claude-haiku-4-5"

  Scenario: KB 與租戶皆未設定時採用環境預設
    Given 知識庫 ocr_model 為 ""
    And 租戶 default_ocr_model 為 ""
    When 解析 OCR 引擎
    Then 應選用 Claude Vision 引擎
    And 引擎 model spec 應為 "anthropic:claude-sonnet-4-6"

  Scenario: 相同 spec 重複解析時共用同一個引擎實例
    Given 知識庫 ocr_model 為 "google:gemini-3.7-flash"
    And 租戶 default_ocr_model 為 ""
    When 解析 OCR 引擎兩次
    Then 兩次應取得同一個引擎實例

  # ── KB 儲存驗證 ──

  Scenario: 建立知識庫時指定未知供應商應回傳驗證錯誤
    When 以 ocr_model "foo:bar-vision" 建立知識庫
    Then 應回傳驗證錯誤且訊息包含 "foo"
    And 知識庫不應被儲存

  Scenario: 更新知識庫時指定未知供應商應回傳驗證錯誤
    Given 一個既有知識庫
    When 以 ocr_model "ollama:llava" 更新知識庫
    Then 應回傳驗證錯誤且訊息包含 "ollama"
    And 知識庫不應被更新

  Scenario: 更新知識庫時清空 ocr_model 應被接受
    Given 一個既有知識庫
    When 以 ocr_model "" 更新知識庫
    Then 知識庫應更新 ocr_model 為 ""

  # ── OpenAI 相容引擎行為 ──

  Scenario: 相容引擎解析回應用量並回傳 token 數
    Given 一個 google 相容引擎 "google:gemini-3.7-flash"
    And 相容端點回應文字 "商品：可口可樂" 且用量 prompt_tokens 1200、completion_tokens 80
    When 對一張 PNG 圖片執行 OCR
    Then OCR 結果文字應為 "商品：可口可樂"
    And OCR 結果 input_tokens 應為 1200、output_tokens 應為 80
    And OCR 結果 model 應為 "google:gemini-3.7-flash"
    And 送出的請求應以 image_url data URL 附上 "image/png" 圖片
    And 送出的 prompt 應包含抑制幻覺指令

  Scenario: google 模型的頁面分類使用 response_format json_schema
    Given 一個 google 相容引擎 "google:gemini-3.7-flash"
    And 相容端點回應文字 "{\"page_type\": \"promotion\"}" 且用量 prompt_tokens 900、completion_tokens 6
    When 對一張 PNG 圖片執行頁面分類
    Then 送出的請求應包含 json_schema response_format
    And 頁面分類結果應為 "promotion"
    And 分類結果 input_tokens 應為 900、output_tokens 應為 6

  Scenario: 非原生 schema 供應商的頁面分類以純 prompt 並容錯解析
    Given 一個 google 相容引擎 "openrouter:qwen/qwen-vl"
    And 相容端點回應文字 "Cover." 且用量 prompt_tokens 500、completion_tokens 2
    When 對一張 PNG 圖片執行頁面分類
    Then 送出的請求不應包含 response_format
    And 頁面分類結果應為 "cover"

  Scenario: API key 缺失時回傳與 Claude 引擎一致的認證錯誤
    Given 一個 google 相容引擎 "google:gemini-3.7-flash" 且供應商未設定 API key
    When 對一張 PNG 圖片執行 OCR
    Then 應拋出 OcrProcessingError 且訊息包含 "auth error"

  Scenario: 端點回應 401 時回傳認證錯誤
    Given 一個 google 相容引擎 "google:gemini-3.7-flash"
    And 相容端點回應 HTTP 401
    When 對一張 PNG 圖片執行 OCR
    Then 應拋出 OcrProcessingError 且訊息包含 "auth error"

  # ── 用量記帳 ──

  Scenario: 文件處理的 OCR 用量記帳 model 為實際 spec
    Given 知識庫 ocr_model 為 "google:gemini-3.7-flash"
    And 假引擎每頁回傳 input_tokens 100、output_tokens 10
    When 處理一份 PNG 文件
    Then 應記錄一筆 ocr 用量 model 為 "google:gemini-3.7-flash"
    And 該筆用量 input_tokens 應為 100、output_tokens 應為 10

  Scenario: 兩份不同 spec 的文件並行處理時用量互不干擾
    Given 文件 A 的知識庫 ocr_model 為 "google:gemini-3.7-flash" 且假引擎每頁回傳 input_tokens 100、output_tokens 10
    And 文件 B 的知識庫 ocr_model 為 "anthropic:claude-haiku-4-5" 且假引擎每頁回傳 input_tokens 7、output_tokens 3
    When 並行處理文件 A 與文件 B
    Then 文件 A 應記錄 ocr 用量 model "google:gemini-3.7-flash" input_tokens 100、output_tokens 10
    And 文件 B 應記錄 ocr 用量 model "anthropic:claude-haiku-4-5" input_tokens 7、output_tokens 3

  Scenario: 重新處理文件時 ocr_model 覆寫優先於 KB 設定
    Given 知識庫 ocr_model 為 "anthropic:claude-haiku-4-5"
    And 假引擎每頁回傳 input_tokens 50、output_tokens 5
    When 以 ocr_model "google:gemini-3.7-flash" 重新處理一份 PNG 文件
    Then 應記錄一筆 ocr 用量 model 為 "google:gemini-3.7-flash"
