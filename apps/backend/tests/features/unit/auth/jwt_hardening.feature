Feature: JWT 改版 (JWT Hardening)
    身為平台資安負責人
    我想要每一張票都帶 iss / aud / jti / iat 與 kid，且 production 不接受舊格式
    以便票能被撤銷、被輪替、不被拿去別的服務重放

    Scenario Outline: 各票種一律帶標準 claims 與 kid
        Given 簽發者 "agentic-rag" 受眾 "agentic-rag-api" kid "k1" 的 JWT 服務
        When 簽發 "<kind>" 票
        Then 票的 iss 為 "agentic-rag" aud 為 "agentic-rag-api" type 為 "<type>"
        And 票帶有 jti 與 iat
        And 票的 header kid 為 "k1"

        Examples:
            | kind           | type           |
            | tenant_access  | tenant_access  |
            | user_access    | user_access    |
            | refresh        | refresh        |
            | tenant_refresh | tenant_refresh |
            | api_access     | api_access     |

    Scenario: user 票與 refresh 票帶 ver，refresh 另帶 family
        Given 簽發者 "agentic-rag" 受眾 "agentic-rag-api" kid "k1" 的 JWT 服務
        When 簽發 user "u1" 租戶 "t1" ver 3 family "fam-1" jti "j-1" 的 refresh 票
        Then 票的 ver 為 3 family 為 "fam-1" jti 為 "j-1"

    Scenario Outline: 錯的 iss / aud 一律拒絕
        Given 簽發者 "agentic-rag" 受眾 "agentic-rag-api" kid "k1" 的 JWT 服務
        When 以相同 secret 偽造 iss "<iss>" aud "<aud>" 的票
        Then 解析應失敗

        Examples:
            | iss         | aud             |
            | other       | agentic-rag-api |
            | agentic-rag | other-service   |

    Scenario Outline: 無 iss 的 legacy 票依設定決定是否接受
        Given 允許 legacy 為 <allow> 的 JWT 服務
        When 以相同 secret 簽一張無 iss / aud 的舊票
        Then 解析結果應為 <outcome>

        Examples:
            | allow | outcome |
            | True  | 成功    |
            | False | 失敗    |
