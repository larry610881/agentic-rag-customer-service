Feature: 安全標頭與文件端點關閉 (Security Headers / Docs Exposure)
    身為資安負責人
    我想要所有回應帶齊安全標頭、API 回應不可快取、production 不公開 API 文件
    以便送檢時 11365 / 11366 / 11359 / 11306 / 10820 不再被列

    Scenario: 一般回應帶齊安全標頭
        Given 掛上安全標頭中介層的應用
        When 請求 "/admin/"
        Then 回應標頭 "Strict-Transport-Security" 應含 "max-age=31536000"
        And 回應標頭 "X-Content-Type-Options" 應為 "nosniff"
        And 回應標頭 "X-Frame-Options" 應為 "DENY"
        And 回應標頭 "Content-Security-Policy" 應含 "frame-ancestors 'none'"
        And 回應標頭 "Referrer-Policy" 應為 "strict-origin-when-cross-origin"

    Scenario: API 回應不可快取
        Given 掛上安全標頭中介層的應用
        When 請求 "/api/v1/things"
        Then 回應標頭 "Cache-Control" 應為 "no-store"

    Scenario: 非 API 路徑不強制 no-store
        Given 掛上安全標頭中介層的應用
        When 請求 "/static/widget.js"
        Then 回應不應有標頭 "Cache-Control" 值為 "no-store"

    Scenario: 路由已設定的 Cache-Control 不被覆蓋
        Given 掛上安全標頭中介層的應用
        When 請求 "/api/v1/cached"
        Then 回應標頭 "Cache-Control" 應為 "private, max-age=60"

    Scenario Outline: 依環境決定 API 文件是否公開
        When 以 app_env "<env>" 計算 FastAPI 文件參數
        Then docs_url 應為 <docs>

        Examples:
            | env         | docs      |
            | production  | None      |
            | development | /docs     |
