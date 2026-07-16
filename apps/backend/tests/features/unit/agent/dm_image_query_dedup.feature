Feature: DM 圖卡查詢的去重與 context 組裝分離
  圖卡（sources）同頁去重避免 LINE carousel 重複顯示，
  但 LLM 的 context 文字必須保留去重前所有命中商品，
  否則同頁次高分商品會從 AI 視野消失（POC 問題 7 包大人案例）。

  Scenario: 同頁兩個相關商品時 context 保留全部而圖卡只出一張
    Given DM 第 49 頁有幫寶適與包大人兩個商品且第 50 頁有寵物物語
    When 使用者查詢「包大人尿布有優惠嗎」
    Then 圖卡清單只包含 2 張（第 49 頁與第 50 頁各一）
    And context 文字同時包含「幫寶適」「包大人」「寵物物語」

  Scenario: 檢索無結果時回傳空 context 與空圖卡
    Given DM 知識庫查無相關商品
    When 使用者查詢「不存在的商品」
    Then 回傳空 context 與空圖卡清單
