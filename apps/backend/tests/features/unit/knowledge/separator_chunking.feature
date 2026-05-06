Feature: Separator-Based Chunking (DM 商品目錄)
  DM 目錄 OCR 輸出的 === 分隔符是天然商品邊界。Separator splitter 按 ===
  切，1 商品 = 1 chunk，並把頁面【...】markers 與【頁面級促銷說明】抽進
  context_text，讓 embedding 自動帶入頁面 metadata。

  Scenario: 頁面有 3 個商品區塊應產生 3 個 chunks 且 context_text 含頁面 metadata
    Given OCR 文本含【商家】全聯與【頁面分類】商品頁與 3 個 === 分隔的商品區塊
    When 我用 separator splitter 切塊
    Then 應產生 3 個 chunks
    And 每個 chunk 的 content 應對應一個商品區塊
    And 每個 chunk 的 context_text 應包含「全聯」
    And 每個 chunk 的 context_text 應包含「商品頁」

  Scenario: 頁面尾部【頁面級促銷說明】應抽到 context_text
    Given OCR 文本含 2 個商品區塊與尾部頁面級促銷說明 滿309折30
    When 我用 separator splitter 切塊
    Then 應產生 2 個 chunks
    And 每個 chunk 的 context_text 應包含「滿309折30」

  Scenario: 純文字無 === 分隔符應 fallback
    Given OCR 文本為一般段落無分隔符
    When 我用 separator splitter 切塊
    Then 應呼叫 fallback splitter 切塊

  Scenario: 只有頁面 metadata 無商品區塊應 fallback
    Given OCR 文本只有【商家】markers 但無 === 分隔符
    When 我用 separator splitter 切塊
    Then 應呼叫 fallback splitter 切塊
