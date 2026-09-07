Feature: 防護階段設定 API（Issue #75）— 前端契約對證

  以真實 router + PostgreSQL 驗證前端 /admin/guard-control、/guard-status 與 bot 表單所依賴的
  四個契約假設：租戶 PUT 的 null 語意、總覽含內建方案、方案新增／沿用、租戶 profile 永不為 null；
  以及 bot 超集／鎖定規則、/guard/effective 的形狀與租戶端變更紀錄的「平台」標記。

  Background:
    Given 系統管理員已登入
    And 已建立租戶 "guard-co" 並以 tenant_admin 登入

  Scenario: 總覽在空資料庫下回內建方案、程式預設底線與可用階段
    When 系統管理員 GET 防護總覽
    Then 總覽的 profiles 含內建 standard（空）與 exhibition（不含 classifier_attack）
    And 總覽的 builtin_profiles 為 exhibition、standard
    And 總覽的 effective_default 底線為 regex_input、output_guard、abuse_scoring 且 profile 為 standard
    And 總覽的 stages 為五個可用階段

  Scenario: 未設定過的租戶 profile 為 standard（非 null）且可由 tenant_admin 讀自己
    When 系統管理員 GET 租戶 "guard-co" 的防護設定
    Then 租戶設定的 profile 為 "standard"、locked 為 false、overrides 為空、editable 為 true
    When tenant_admin GET 自己租戶的防護設定
    Then 回應狀態為 200 且 editable 為 false
    When tenant_admin GET 租戶 "other-tenant-id" 的防護設定
    Then 回應狀態為 403

  Scenario: 租戶 PUT 整列取代；profile / locked 送 null 會把鍵刪掉而非「不變更」
    When 系統管理員 PUT 租戶 "guard-co" 防護 profile "exhibition"、加開 classifier_attack、locked true
    Then 回應狀態為 200 且 overrides 含 profile exhibition、locked true、stages classifier_attack
    When 系統管理員 PUT 租戶 "guard-co" 防護 profile null、overrides 空、locked null
    Then 回應狀態為 200 且 overrides 為空
    When 系統管理員 GET 租戶 "guard-co" 的防護設定
    Then 租戶設定的 profile 為 "standard"、locked 為 false、overrides 為空、editable 為 true

  Scenario: 租戶 PUT 指定未知方案回 422
    When 系統管理員 PUT 租戶 "guard-co" 防護 profile "nope"
    Then 回應狀態為 422 且 detail 含 "Unknown profile"

  Scenario: 方案 PUT 未知名稱即新增；overrides 空物件即沿用系統預設；非法鍵與階段回 422
    When 系統管理員 PUT 方案 "vip" stages 為 regex_input、classifier_attack、output_guard、abuse_scoring
    Then 回應狀態為 200 且 scope_kind 為 "profile"
    When 系統管理員 GET 防護總覽
    Then 總覽的 profiles 含 "vip" 且其 stages 有四段
    When 系統管理員 PUT 方案 "vip" overrides 空物件
    Then 回應狀態為 200
    When 系統管理員 GET 防護總覽
    Then 總覽的 profiles 含 "vip" 且為空覆寫
    When 系統管理員 PUT 方案 "vip" stages 含未知階段 "bogus"
    Then 回應狀態為 422 且 detail 含 "Unknown guard stage"
    When 系統管理員 PUT 方案 "vip" overrides 含 required_stages
    Then 回應狀態為 422

  Scenario: 展覽方案下租戶加開分類器會生效（來源 tenant）；鎖定後租戶覆寫被忽略
    When 系統管理員 PUT 租戶 "guard-co" 防護 profile "exhibition"、加開 classifier_attack、locked false
    And 系統管理員 GET 租戶 "guard-co" 的防護設定
    Then 租戶有效階段含 classifier_attack 且來源為 tenant
    When 系統管理員 PUT 租戶 "guard-co" 防護 profile "exhibition"、加開 classifier_attack、locked true
    And 系統管理員 GET 租戶 "guard-co" 的防護設定
    Then 租戶有效階段不含 classifier_attack 且 locked 為 true

  # 注意：bot PUT 的 guard_stages 違規由 bot_router 的 domain ValidationError 處理 → 400（非 guard 路由的 422）
  Scenario: bot guard_stages 必須是租戶有效集合的超集；鎖定時不得自設；有效值端點回 bot 來源與全集
    Given tenant_admin 已建立 Bot "guard-bot"
    When tenant_admin PUT Bot guard_stages 為 regex_input、output_guard
    Then 回應狀態為 400 且 detail 含 "cannot remove"
    When tenant_admin PUT Bot guard_stages 為 regex_input、classifier_attack、output_guard、abuse_scoring、local_classifier
    Then 回應狀態為 200 且 Bot 的 guard_stages 有五段
    When tenant_admin GET Bot 的有效防護
    Then 有效防護含 tenant_id、bot_id、五個 available_stages，且 local_classifier 來源為 bot
    When tenant_admin GET 有效防護但不帶 bot_id
    Then 回應狀態為 422
    When 系統管理員 PUT 租戶 "guard-co" 防護 profile "standard"、overrides 空、locked true
    And tenant_admin PUT Bot guard_stages 為 regex_input、classifier_attack、output_guard、abuse_scoring、local_classifier
    Then 回應狀態為 400 且 detail 含 "locked"

  Scenario: 系統管理員改租戶防護後，租戶 bot 變更紀錄可見且標「平台」
    Given tenant_admin 已建立 Bot "guard-bot"
    When 系統管理員 PUT 租戶 "guard-co" 防護 profile "exhibition"、加開 classifier_attack、locked true
    And tenant_admin GET Bot 的變更紀錄
    Then 變更紀錄含一筆 entity_type guard_settings、actor_label "平台"
