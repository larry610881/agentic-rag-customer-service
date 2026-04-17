---
name: Project Deployment Phase
description: 專案部署階段旗標。Claude 依此判斷 migration / DDL / 直連 DB 等危險操作是否允許。切換此檔案需 Larry 明確批准。
---

# Current Phase

**phase**: `poc-dev`

**切換記錄**：
- 2026-04-17 — 初始化，POC 個人開發階段。

---

## Phase 定義

| Phase | 說明 | DB DDL 執行路徑 |
|-------|------|----------------|
| `poc-dev` | 個人 POC / 本地 + 個人 GCP VM 開發 | ✅ Claude 可連 dev DB 直接執行 DDL（需 review + verify + 紀錄） |
| `pre-prod` | 即將上測試機 / UAT / 有外部測試使用者 | ❌ 禁止 Claude 直連 DB，只能寫 SQL 檔 + 請 Larry 或 DBA 人工套用 |
| `production` | 正式環境 | ❌ 禁止 Claude 直連 DB，所有 DDL 走 CI/CD pipeline |

## 切換規則

- **只能由 Larry 明確宣告切換**（例如：「改階段：pre-prod」或直接改此檔案），Claude 不得主動切換
- 切換時在「切換記錄」加一行（日期 + 理由）
- 切換到 `pre-prod` 或 `production` 後，`.claude/rules/migration-workflow.md` 會自動禁止所有 DDL 直連指令

## 觸發切換的常見訊號

- SPRINT_TODOLIST 出現「部署測試機」「UAT 名單」「對外開放」等任務
- 租戶數量 > 1（有外部租戶接入）
- Bot 接入正式 LINE 官方帳號 / 網站
- 需要符合資料保護 / 合規要求（GDPR / 個資法）

若 Claude 觀察到這些訊號，應主動提醒 Larry 評估是否切換 phase，但仍須 Larry 明確確認才能改。
