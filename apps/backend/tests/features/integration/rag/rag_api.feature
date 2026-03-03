Feature: RAG Query API Integration
  使用真實 DB 驗證 RAG 查詢端點（外部服務 mocked）

  Background:
    Given 已登入為租戶 "RAG Corp"
    And 已建立知識庫 "FAQ"

  Scenario: 查詢不存在的知識庫回傳 404
    When 我送出 RAG 查詢到不存在的知識庫
    Then 回應狀態碼為 404

  Scenario: 未認證時拒絕存取
    When 我不帶 token 送出 POST /api/v1/rag/query
    Then 回應狀態碼為 401
