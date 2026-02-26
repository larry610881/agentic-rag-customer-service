Feature: 文件品質回饋關聯統計
  身為知識庫管理員
  我希望看到哪些文件被差評引用
  以便我優先改善這些文件的分塊品質

  Scenario: 有差評的文件 — 回傳 negative_feedback_count
    Given 知識庫有文件 "faq.txt" 且有差評引用其 chunks
    When 查詢品質統計
    Then "faq.txt" 的 negative_feedback_count 應大於 0

  Scenario: 無差評的文件 — negative_feedback_count 為 0
    Given 知識庫有文件 "guide.txt" 且沒有差評
    When 查詢品質統計
    Then "guide.txt" 的 negative_feedback_count 應為 0
