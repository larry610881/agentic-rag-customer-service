# Full Review 2026-08-20 — 修復總結（驗收對照表）

> 對應報告：`docs/reviews/full-review-2026-08-20.md`（104 findings）
> 分支：`fix/critical-c1-c3-publish-widget-billing`（50 commits）
> 目的：換新環境一次性全量驗收 → 公開給業務接客戶前的最終品質關卡。

## 總覽

| 嚴重度 | 總數 | 已修復 | 延後（有明確理由與排期） |
|--------|------|--------|--------------------------|
| CRITICAL | 9  | 9  | 0 |
| HIGH     | 20 | 20 | 0 |
| MEDIUM   | 53 | 51 | 2（M12、M23-at-rest 部分） |
| LOW      | 22 | 22 | 0 |

## 延後項目（僅 2 項，均有部分緩解 + 排期）

### M12 — SSE 客戶端中斷 → 該輪 token 漏記
- **為何延後**：正確修法是把 usage 記帳移入 `execute_stream` 產生 usage 當下即
  落帳（router 事後補記在中斷時必然漏）。這需要把 record_usage 注入
  send_message_use_case、request_type/run_id 穿透 command、web+widget 兩個
  router 同步停用舊記帳——倉促改動有 double-billing 風險。攻擊窗口極窄
  （內容 token 串完到 usage 事件間的毫秒級間隙），兩名反駁者建議降 LOW。
- **排期**：已明文列入 `channel-parity.md` 債務 #5（usage 記帳路徑統一）。

### M23（部分） — LINE 憑證 DB at-rest 加密
- **已修復的部分**：API 回應遮罩（`***`，update 時 `***`=未變更，比照 mcp
  env_values 慣例）；Redis 快取加密存放（L10）；跨租戶讀取面已由 C8 關閉。
- **為何延後 at-rest**：DB 欄位加密需要「加密既有明文資料」的 data migration
  （依 migration 工作流須逐環境授權執行），且 `infra/setup-worker-vm.sh:40`
  硬編碼的 ENCRYPTION_MASTER_KEY 必須一併輪替——金鑰管理需 Larry 決策。
- **殘餘暴露面**：僅 DB dump／備份外流（後入侵情境）。

## 依報告推遲、以標注/排期取代直接修的項目

- **M21（LINE 無 memory）**：報告提供的兩個修法中選了「排入債務清單」——
  強行接線違反 channel-parity 的絞殺者紀律（先抽共用 service、家樂福 LINE
  零回歸）。已列 `channel-parity.md` 債務 #6。
- **M22（replay 走 web 管線近似）**：replay 結果 `details` 已加
  `pipeline_approximation: "web"` 誠實標注；完整保真列債務 #7。

## 驗證狀態（2026-08-21）

| 檢查 | 結果 |
|------|------|
| 後端 unit（1350 tests） | ✅ 全綠 |
| 後端 integration | 142 passed / 39 failed——39 個全屬**既有**環境依賴失敗（真 LLM API 401、外部服務），修復前基線為 43 個，零新增 |
| 前端 vitest（279 tests） | ✅ 全綠（含補課修復的既有 i18n/fixture drift） |
| ruff / eslint / tsc | 所有改動檔案零新增錯誤（與 origin 逐檔比對） |
| mypy | 新增碼僅重現既有可接受模式（`Result.rowcount`），零新類別 |

## 重點修復摘要（依風險類別）

### 安全 / 租戶隔離
- C 系列全修（publish gate、跨租戶 conversation/dataset/bot IDOR、widget billing）。
- M11 test-back 後門刪除；M13 guard 細節暴露改 JWT role 判定。
- M24 生產環境拒絕預設密鑰啟動；M36 optimizer prompt 讀寫綁 tenant。
- M43 登出清 TanStack Query 快取（跨租戶快取洩漏）；L4 quota 標記逃逸封鎖；
  L11 feedback 標籤跨租戶注入封鎖；L10/M23 LINE 憑證 Redis 加密 + API 遮罩。

### 併發 / 狀態機（閘門核心）
- M2 取號+INSERT 重試（撞唯一約束→409 非 500）。
- M3/M6 版本狀態轉移樂觀鎖（條件式 UPDATE，並發 publish+reject／連點驗證
  只有一方成功），真 DB 整合測試驗證 SQL 層 rowcount=0→409。
- M4 背景任務引用保存（GC 防護）；M5 孤兒版本救援（run 完成但版本卡
  validating）；M7 多實例寬限窗（不殺其他實例健康 run）。

### 資源洩漏（呼應全域 pool-leak 規範）
- M29/H14 啟動任務包 independent_session_scope；M30 arq worker 全 job 包
  scope；L7 LINE httpx client 共用；L22 blob URL revoke。

### Eval / Optimizer 正確性
- M28 API 故障不再偽造 0 分假 FAIL（>50% 失敗整輪作廢 502 + refresh_token 續期）。
- M32 validate/eval/CLI 三處補多輪 conversation_history。
- M35 import 斷言去重；M34 CLI 中斷回寫 best；M33 壞 params 單斷言失敗不炸 run；
  L13 budget 計實際呼叫；L14 event loop 收尾；L15 meta-prompt 注入定界。

### LINE 通路
- M15 驗簽 403/bot 404 + 背景處理防 redelivery 重覆回覆；M18 群組事件不再
  毒殺整批；M16/M17/M19 worker 參數三通路一致；M20/H10 trace outcome/來源。

### 前端
- M40/M41/L19 快取失效補齊；M42/L20 401 迴圈與登入誤判；M44 SSE 收尾；
  M45 Studio DAG 凍結；M46/M47 分頁夾回與勾選修剪；L16-L18、L21 小修。

### 測試品質（M48-M53）
- 孤兒清理/樂觀鎖已有真 SQL 整合測試；shadow 隔離斷言去 vacuous 化；
  gate run 背景三分支（預算中止/API 錯誤/P0-only round）；前端補 gate/replay
  報告分支渲染與 mutation endpoint 契約測試。

## 驗收注意事項

1. **新環境部署後**：M24 會使**未設定 JWT_SECRET / ENCRYPTION_MASTER_KEY 的
   生產部署直接拒絕啟動**（fail-fast by design）——請先設好環境變數。
2. **LINE 憑證表單**：GET 現在回 `***`；表單原樣送回=不變更、清空=清除。
3. **39 個既有整合測試失敗**為外部依賴類（真 API 金鑰/外部服務），非本次
   回歸；如需全綠需在有金鑰的環境跑或另行 mock。
4. eval/validate 端點新增選填 `refresh_token` body 欄位（前端已帶）。
