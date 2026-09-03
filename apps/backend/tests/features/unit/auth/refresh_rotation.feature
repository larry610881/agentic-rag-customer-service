Feature: Refresh 旋轉與撤銷 (Refresh Rotation & Revocation)
    身為後台使用者
    我希望 refresh token 每次換票就作廢、被偷用時整組登入失效、改密碼後舊票立即失效
    以便 7 天的 refresh 不會變成長期後門

    Background:
        Given 使用者 "u1" 租戶 "t1" 角色 "user" token_version 1
        And 記憶體版 refresh / 撤銷儲存

    Scenario: 登入時登記 refresh family
        When 使用者 "u1" 以正確密碼登入
        Then 登入回傳的 refresh 票帶 family 與 jti 且 family 已登記

    Scenario: 換票後舊 refresh 票作廢、新票可再換
        Given 使用者 "u1" 已登入取得 refresh 票
        When 以該 refresh 票換票
        Then 換票成功且新的 refresh 票 family 相同 jti 不同
        When 再以原本的 refresh 票換票
        Then 換票應失敗
        And family 已被撤銷
        When 以最新的 refresh 票換票
        Then 換票應失敗

    Scenario: ver 不符的 refresh 票被拒
        Given 使用者 "u1" 已登入取得 refresh 票
        And 使用者 "u1" 的 token_version 變為 2
        When 以該 refresh 票換票
        Then 換票應失敗

    Scenario: 改密碼會遞增 token_version 並登記撤銷
        When 使用者 "u1" 以舊密碼 "OldPass123" 改為 "NewPass456"
        Then 使用者 "u1" 的 token_version 應為 2
        And 撤銷儲存記錄 "u1" 最低 ver 為 2

    Scenario: 舊格式（無 family）的 refresh 票仍可換一次並開新 family
        Given 一張使用者 "u1" 無 family 的 refresh 票
        When 以該 refresh 票換票
        Then 換票成功且新的 refresh 票帶 family
