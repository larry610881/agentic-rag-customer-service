# Architecture Learning Journal

> 每次 Sprint / 功能完成後的架構學習筆記彙總。
> 用途：定期回顧、撰寫技術 blog、面試準備、團隊分享。
>
> 格式：每則筆記包含「Sprint 來源 → 主題 → 做得好 → 潛在隱憂 → 延伸學習」。

---

## 目錄

- [LINE Webhook 效能最佳化全鏈路 — gRPC + 連線池 + 並行查詢](#line-webhook-效能最佳化全鏈路--grpc--連線池--並行查詢)
- [LINE Loading Animation + Webhook 效能最佳化](#line-loading-animation--webhook-效能最佳化)
- [RAG Tool 重構 — 消除重複 LLM 呼叫](#rag-tool-重構--消除重複-llm-呼叫)
- [RAG Pipeline 效能 Trace — 分段計時 Instrumentation](#rag-pipeline-效能-trace--分段計時-instrumentation)
- [Streaming UX 分段 Hint + 寒暄路由優先修復](#streaming-ux-分段-hint--寒暄路由優先修復)
- [簡化 LLM Provider 架構 — Static Selector 移除 + Debug-Only UI 控制](#簡化-llm-provider-架構--static-selector-移除--debug-only-ui-控制)
- [Multi-Tenant System Admin — 獨立 Tenant + 跨租戶唯讀總覽](#multi-tenant-system-admin--獨立-tenant--跨租戶唯讀總覽)
- [Request Log Viewer — 異步 Fire-and-Forget 寫入 + Cross-Cutting 診斷工具](#request-log-viewer--異步-fire-and-forget-寫入--cross-cutting-診斷工具)
- [Embedding 全站單一模型 + API Key 管理 + 401 自動登出](#embedding-全站單一模型--api-key-管理--401-自動登出)
- [Provider Settings 模型 DB 化 + Bot 模型選擇](#provider-settings-模型-db-化--bot-模型選擇)
- [DeepSeek Provider 集成 + Provider Settings 兩層開關簡化](#deepseek-provider-集成--provider-settings-兩層開關簡化)
- [Frontend Framework Migration — Next.js 16 → React + Vite SPA](#frontend-framework-migration--nextjs-16--react--vite-spa)
- [PostgreSQL 連線洩漏修復 — ContextVar Session 生命週期管理](#postgresql-連線洩漏修復--contextvar-session-生命週期管理)
- [Frontend E2E User Journeys — 雙角色覆蓋全功能](#frontend-e2e-user-journeys--雙角色覆蓋全功能)
- [Issue #15 隱憂修復 — Reprocess Task Tracking + Cross-BC JOIN](#issue-15-隱憂修復--reprocess-task-tracking--cross-bc-join)
- [Issue #15 — Chunk Quality Monitoring 品質指標 + 回饋關聯](#issue-15--chunk-quality-monitoring-品質指標--回饋關聯)
- [Issue #9 — API Rate Limiting + User Auth 身份體系](#issue-9--api-rate-limiting--user-auth-身份體系)
- [Issue #8 — Embedding 429 Rate Limit + Adaptive Batch Size](#issue-8--embedding-429-rate-limit--adaptive-batch-size)
- [Issue #7 — Integration Test Deadlock 根因修復](#issue-7--integration-test-deadlock-根因修復)
- [Issue #7 — Integration Test 基礎設施建立](#issue-7--integration-test-基礎設施建立)
- [E6 — Content-Aware Chunking Strategy](#e6--content-aware-chunking-strategy)
- [E5 — Redis Cache 統一遷移](#e5--redis-cache-統一遷移)
- [E4 — EventBus 死代碼移除 + Redis Cache 規劃](#e4--eventbus-死代碼移除--redis-cache-規劃)
- [E3 — 邊緣問題批次修復（Edge Case Batch Fix）](#e3--邊緣問題批次修復edge-case-batch-fix)
- [E2 完整版 — 企業級回饋分析系統](#e2-完整版--企業級回饋分析系統)
- [E2 MVP — 回饋收集 + Web/LINE 雙通路](#e2-mvp--回饋收集--webline-雙通路)
- [E1.5 — LINE Webhook 多租戶](#e15--line-webhook-多租戶)
- [E1 — System Provider Settings DB 化](#e1--system-provider-settings-db-化)
- [E0 — Tool 清理 + Multi-Deploy](#e0--tool-清理--multi-deploy)
- [S7 — Multi-Agent 2-Tier + Bot Management](#s7--multi-agent-2-tier--bot-management)
- [S6 — Agentic 工作流 + 多輪對話](#s6--agentic-工作流--多輪對話)
- [S5 — 前端 MVP + LINE Bot](#s5--前端-mvp--line-bot)
- [S4 — AI Agent 框架](#s4--ai-agent-框架)

---

## LINE Webhook 效能最佳化全鏈路 — gRPC + 連線池 + 並行查詢

> **Sprint 來源**：LINE Bot 效能調教（對標競品 5 秒回覆）
> **變更範圍**：Infrastructure（Qdrant gRPC + httpx 持久 client × 4 service）+ Application（asyncio.gather 並行 KB 查詢）+ Tests

### 本次相關主題

Per-bot LLM 模型選擇、Qdrant REST→gRPC、httpx 連線池化、asyncio.gather 並行化、LINE Reply+Push 兩階段 webhook

### 做得好的地方

- **全鏈路性能分析**：用 timing log 系統化定位瓶頸（Embedding 2.9-7.2s / Qdrant 1.9-2.7s / GPT-5.1 8.5-9.9s / LINE push 4.3-6.3s），而非盲目猜測
- **Qdrant gRPC**：`qdrant_grpc_port` 設定早已存在但從未接入，只改 2 個檔案即完成，向後相容（`prefer_grpc=False` 為預設值）
- **httpx 連線池化**：統一模式 — 所有 4 個 service（Embedding / OpenAI / Anthropic / LINE）改為 `__init__` 時建立持久 `AsyncClient`，消除每次請求的 TLS 握手開銷
- **asyncio.gather**：RAG 多知識庫查詢從 sequential loop 改為並行，對多 KB bot 效果顯著
- **兩階段 webhook**：`prepare_and_reply()` 直接 await（秒回「查詢中」）+ `process_and_push()` 背景執行，LINE 使用者體感大幅改善

### 潛在隱憂

- **httpx 持久 client 生命週期** → 若 service 被 GC 但 client 未 close，可能有 fd leak。目前 service 是 Singleton/Factory 由 DI container 管理，隨 process 存活，風險低。未來若需優雅關閉，可加 `async def close()` + FastAPI shutdown event → **優先級：低**
- **asyncio.gather 錯誤傳播** → 若其中一個 KB 查詢失敗，`gather` 預設會傳播第一個 exception 並取消其他。目前行為合理（查詢失敗就失敗），但若未來需 partial results，需改用 `return_exceptions=True` → **優先級：低**
- **Qdrant gRPC 連線中斷處理** → gRPC 長連線可能因網路抖動斷開，qdrant-client 內建重連機制，但需觀察生產環境是否有 `grpc._channel._InactiveRpcError` → **優先級：中**

### 延伸學習

- **HTTP/2 Connection Pooling**：httpx 持久 client 自動利用 HTTP/2 multiplexing（若 server 支援），單一 TCP 連線可並行多個請求
- **gRPC vs REST 效能差異**：gRPC 使用 Protocol Buffers 二進位序列化 + HTTP/2 multiplexing，對高頻小 payload（如向量搜尋）效能提升 3-10x
- **若想深入**：搜尋 "qdrant grpc performance benchmark" 或 "httpx connection pool tuning"

---

## LINE Loading Animation + Webhook 效能最佳化

> **Sprint 來源**：LINE Bot UX 改善
> **變更範圍**：Domain（show_loading ABC）+ Infrastructure（LINE API 呼叫）+ Application（fire-and-forget + enabled_tools）+ Tests（2 BDD scenarios）

### 做得好的地方
- 跨 DDD 4 層完整實作：Domain 抽象 → Infrastructure 實作 → Application 編排 → Tests 驗證，遵循分層原則
- `show_loading` 採 `asyncio.create_task()` fire-and-forget，不阻塞 `process_message`，省 ~500-1000ms
- 發現 `execute_for_bot()` 漏傳 `enabled_tools`，導致 router 每次跑 LLM 意圖分類（Web 端早已跳過），補上後再省 ~500-800ms
- 修正根因是「呼叫端參數不一致」而非重寫 router 邏輯，維持單一程式碼路徑

### 潛在隱憂
- `HttpxLineMessagingService` 每個方法都建新 `httpx.AsyncClient()`（TLS handshake 重複開銷）→ 可改為 `__init__` 建一次 client 重複使用 → 優先級：中
- `show_loading` fire-and-forget 的例外會靜默丟失 → 可加 `task.add_done_callback` 記錄錯誤 → 優先級：低
- `execute()`（舊端點）仍未傳 `enabled_tools`，走 LLM 分類 → 若仍有流量應一併修正 → 優先級：低

### 延伸學習
- **Fire-and-Forget Pattern**：適合「不影響主流程結果」的副作用操作（通知、日誌、預載），但需注意例外處理與背壓控制
- **參數一致性檢查**：同一 Use Case 的不同入口（Web vs LINE）若行為不同，往往是參數遺漏而非架構差異，code review 時應比對所有呼叫端

---

## RAG Tool 重構 — 消除重複 LLM 呼叫

> **Sprint 來源**：效能優化（RAG pipeline UX hint 時間不對齊）
> **變更範圍**：Application（QueryRAGUseCase.retrieve）+ Infrastructure（RAGQueryTool）

### 做得好的地方
- 透過 Cloud Run log 分段計時精準定位瓶頸：30 秒中 Qdrant 只佔 44ms，LLM 佔 30s
- 新增 `retrieve()` 方法遵循 SRP（Single Responsibility）：`execute()` = 完整 RAG（含 LLM），`retrieve()` = 純檢索
- 修改後 LLM 只在 streaming Phase 2 呼叫一次，省掉重複的 token 費用

### 潛在隱憂
- `execute()` 和 `retrieve()` 有重複的 embed + search 邏輯 → 可抽取共用 `_search_chunks()` 私有方法 → 優先級：低
- Agent 非 streaming 路徑（`process_message`）的 respond node 仍使用 `agent_graph.py` 內的 `_make_respond_node`，該路徑也會受益但未驗證 → 優先級：低

### 延伸學習
- **CQRS 拆分粒度**：`execute()` vs `retrieve()` 是同一 Use Case 內的讀模型拆分。若未來 retrieve 和 generate 需要獨立擴展，可拆為兩個獨立 Use Case
- **Observability-Driven Development**：本次先加 timing log → 發現瓶頸 → 修復，是典型的「先量測再優化」模式

---

## RAG Pipeline 效能 Trace — 分段計時 Instrumentation

> **Sprint 來源**：效能診斷（自建 VM Qdrant 慢查詢）
> **變更範圍**：Application（QueryRAGUseCase） + Infrastructure（QdrantVectorStore）

### 做得好的地方
- 使用 `time.perf_counter()` 精確計時，拆分 embed / search / llm 三段延遲
- 利用 structlog 結構化 log（`embed_ms=`, `search_ms=`, `llm_ms=`），方便 grep 和 log aggregation
- 在 Infrastructure 層（Qdrant）和 Application 層（Use Case）各留一層計時，可區分「純向量搜尋」vs「整體 RAG 流程」

### 潛在隱憂
- 目前 `execute_stream` 路徑未加計時，streaming 場景下無法診斷 → 建議後續補上 → 優先級：低
- 自建 Qdrant 若未建 payload index（`tenant_id`），filter 查詢會退化為全表掃描 → 建議為所有 collection 建立 keyword index → 優先級：高

### 延伸學習
- **Qdrant Payload Index**：對 filter 欄位建 keyword/integer index，避免暴力掃描。與 RDBMS 的 B-tree index 概念類似
- **Observability 三支柱**：本次加了 Logging（計時 log），未來可考慮 Tracing（OpenTelemetry span）和 Metrics（Prometheus histogram）做完整可觀測性

---

## Streaming UX 分段 Hint + 寒暄路由優先修復

> **來源**：Streaming UX hint 分段 + 🏃 RunnerDots 動畫 + 寒暄路由優先修復
> **日期**：2026-03-05

### 架構學習筆記

**本次相關主題**：SSE 事件協議擴充、Router Priority Chain、前端微動畫

#### 做得好的地方
- **SSE 事件分段**：在 RAG 完成→LLM 生成之間插入 `status` 事件（`rag_done` / `llm_generating`），讓前端能精準切換提示文案，零侵入既有 `tool_calls` / `sources` / `token` 協議
- **Router 優先級修正**：將 keyword 路由提升至 single-tool 捷徑之前，用正則全文匹配（`^寒暄詞[語尾]*$`）實現零延遲攔截，避免「你好」觸發 RAG 查詢
- **動畫與資訊分離**：`ToolHintIndicator` 根據 hint 內容切換渲染模式（普通跳動圓點 vs 🏃 RunnerDots），邏輯集中在一個元件，store 不需改動

#### 潛在隱憂
- **keyword 正則覆蓋率有限**：目前僅涵蓋常見中英文寒暄，方言（阿囉哈）、表情符號（👋）、錯字（你豪）不會命中，可考慮用 LLM 做 fallback 分類 → 優先級：低
- **SSE 事件類型膨脹**：新增 `status` 後共有 7 種事件類型（token / tool_calls / sources / status / usage / conversation_id / done），建議以 TypeScript discriminated union 明確化前後端契約 → 優先級：中

#### 延伸學習
- **Chain of Responsibility**：Router 的判斷順序（keyword → single-tool → LLM）本質上是責任鏈模式，若未來新增更多路由策略（如 intent cache、user preference），可考慮正式抽象為 RouterStrategy chain
- **Optimistic UX**：分段 hint 讓使用者在等待時有更豐富的反饋，這是 Perceived Performance 的經典手法——實際速度不變，但感知速度提升

---

## 簡化 LLM Provider 架構 — Static Selector 移除 + Debug-Only UI 控制

> **來源**：LLM Provider 架構簡化 + tool_calls debug 控制
> **日期**：2026-03-05

### 架構學習筆記

**本次相關主題**：Selector Pattern 退場、Feature Flag（debug gate）、SSE 事件過濾

#### 做得好的地方
- **大幅精簡 Container**：移除 7-branch `_static_llm_service` Selector（~100 行）和 7-branch `agent_service` Selector（~30 行），改為 `Factory(FakeLLMService)` + 2-branch mock/real，所有動態解析交給 `DynamicLLMServiceFactory`
- **Config 瘦身**：移除 `llm_api_key`、`llm_model`、`llm_base_url`、`effective_llm_api_key` 等 4 個已被 DB-driven 架構取代的欄位，加 `extra="ignore"` 相容舊 `.env`
- **SSE 事件分層控制**：`tool_calls` 事件保留傳送（前端 hint 不受影響），僅在非 debug 時清空 `reasoning` 欄位，精確控制資訊暴露粒度

#### 潛在隱憂
- **非 streaming 端點未覆蓋**：`/chat` POST 的 `ChatResponse` 仍包含完整 `tool_calls.reasoning` 不受 debug 控制 → 建議統一在 `execute()` 也加相同過濾 → 優先級：低
- **`extra="ignore"` 風險**：Pydantic Settings 的 `extra="ignore"` 可能隱藏 `.env` 中的拼寫錯誤（如 `LLM_PROVIDER` 拼成 `LLM_PROVDIER` 不會報錯） → 優先級：低

#### 延伸學習
- **Feature Flag vs Configuration**：本次用 `debug` 做 feature gate 是最輕量的方式；若未來需更精細的控制（per-tenant、per-bot），可考慮 Feature Flag Service（如 LaunchDarkly pattern）
- **SSE 事件契約**：前端依賴 `tool_calls` 事件的 `tool_name` 顯示 hint、`reasoning` 顯示詳情；這是隱式契約，建議未來以 TypeScript type + 後端 Pydantic schema 明確化

---

## Multi-Tenant System Admin — 獨立 Tenant + 跨租戶唯讀總覽

> **來源**：架構改進 — system_admin 無法建立知識庫/機器人（FK violation）修復
> **日期**：2026-03-04

### 架構學習筆記

**本次相關主題**：Multi-Tenancy 架構、Domain Entity 不變量、跨租戶權限控制、JWT Claim 設計

#### 做得好的地方
- **DDD 全層變更有序推進**：Domain Entity → Repository Interface → Infrastructure Impl → Application Use Case → Interfaces Router → Container DI，嚴格遵循依賴方向
- **最小侵入式設計**：system_admin 歸屬 System Tenant 而非破壞 FK 約束，保持了資料庫參照完整性
- **Router 層條件分流**：`if tenant.role == "system_admin"` 只在 list 端點分流，POST/PUT/DELETE 保持 tenant 隔離，確保 system_admin 只能修改自己的 System Tenant 資料
- **JWT Claim 自動適配**：因為 `create_user_token()` 已有 `if tenant_id is not None` 邏輯，Domain Entity 改了之後 JWT 自然帶上 tenant_id，無需額外修改
- **前端 JWT 解碼**：login 時直接從 token payload 提取 role，避免額外 API call

#### 潛在隱憂
- **System Tenant 硬編碼風險**：目前 seed script 每次 drop_all 重建，system_tenant_id 會變動。正式環境需要固定 UUID 或配置化 → 建議：環境變數 `SYSTEM_TENANT_ID` 或 DB migration → 優先級：中
- **跨租戶 find_all() 效能**：隨著租戶數增長，`find_all()` 無分頁會成為瓶頸 → 建議：加入 limit/offset 或 cursor-based pagination → 優先級：低
- **前端缺少 role-based route guard**：目前 admin 頁面只靠 sidebar 隱藏，直接輸入 URL 仍可存取（後端有 role 檢查但前端無阻擋） → 建議：新增 `RequireRole` route wrapper → 優先級：中
- **system_admin 的寫入隔離只靠 token 中的 tenant_id**：若 system_admin 構造惡意 request body 帶其他 tenant_id，寫入端點會用 `tenant.tenant_id`（from JWT）而非 body 中的值，這是安全的。但未來若有端點允許 body 指定 tenant_id，需特別注意 → 優先級：低

#### 延伸學習
- **Multi-Tenant Isolation Patterns**：Row-Level Security (RLS) 是 PostgreSQL 原生的租戶隔離機制，比 application-level WHERE 更安全。與本次 application-level `tenant_id` 過濾相關
- **Super-Admin 設計模式**：在 SaaS 系統中，super-admin 常見做法有（1）獨立管理面板無 tenant 概念、（2）歸屬特殊 tenant（本次採用）、（3）tenant_id=NULL + 特殊處理。方案 2 的優點是不破壞 FK 約束且可複用現有 CRUD
- 若想深入：搜尋 "SaaS multi-tenancy patterns" 或 "Row Level Security PostgreSQL multi-tenant"

---

## Request Log Viewer — 異步 Fire-and-Forget 寫入 + Cross-Cutting 診斷工具

> **來源**：Ad-hoc 功能（Cloud Run 日誌可讀性改善）
> **日期**：2026-03-04

### 架構學習筆記

**本次相關主題**：Fire-and-Forget Pattern、Cross-Cutting Concerns、AsyncIO Task 生命週期、DDD 例外豁免

#### 做得好的地方

- **不走完整 DDD 的正確判斷**：Request log 是跨切面的診斷工具，不屬於任何 Bounded Context，直接在 Infrastructure 層處理避免了為診斷功能建立不必要的 Domain Entity / Repository Interface
- **獨立 Session 隔離**：`write_request_log()` 用 `async_session_factory()` 新建 session 而非 request-scoped session，因為寫入時 request 已結束、session 可能已被 `SessionCleanupMiddleware` 關閉
- **吞掉錯誤的設計**：診斷 log 寫入失敗不應影響正常請求，`try/except` 只 warning log 不向上拋
- **`flush_trace()` 回傳值設計**：console 輸出仍受 `TRACE_THRESHOLD_MS` 控制，但 buffer 一律回傳供 DB 寫入，關注點分離乾淨
- **前端 auto-refresh**：`refetchInterval: 10_000` 讓 log viewer 接近即時，不需手動刷新

#### 潛在隱憂

- **`asyncio.create_task()` 未被 await** → 若 app shutdown 時有大量 pending task，可能丟失最後幾筆 log → 可在 `lifespan` shutdown 階段加入 `await asyncio.gather(*pending_tasks)` → 優先級：低（診斷資料丟幾筆可接受）
- **request_logs 表無自動清理** → 長期運行會持續增長 → 建議未來加 `created_at < 30d` 的定時清理 job 或 TTL 策略 → 優先級：中
- **Log viewer API 無 auth** → 目前 log router 在 health 旁邊（always loaded），無需 JWT → 若部署到公開環境需加上 `system_admin` 角色檢查 → 優先級：中
- **JSON column 查詢效能** → `trace_steps` 用 JSON 欄位，目前只做整體存取沒問題，但若未來需 query 內部 step 名稱，MySQL JSON 查詢效能較差 → 優先級：低

#### 延伸學習

- **Structured Concurrency**：Python 3.11+ 的 `TaskGroup` 可取代裸 `create_task()`，提供更好的錯誤傳播和 cancellation 語義。若想深入：搜尋 "Python TaskGroup vs create_task"
- **Application Performance Monitoring (APM)**：本次手刻的 trace 系統本質上是輕量 APM。若規模擴大可考慮 OpenTelemetry 整合，提供標準化的 span/trace 模型。搜尋："OpenTelemetry Python FastAPI integration"
- **Write-Behind Pattern**：目前每個 request 一個 `create_task` 寫 DB。高流量下可改為 buffer + batch flush（類似 Write-Behind Cache），減少 DB 連線壓力。搜尋："write-behind pattern database"

---

## Embedding 全站單一模型 + API Key 管理 + 401 自動登出

**來源**：Embedding 系統級控制 + API Key 管理 + UX 修正
**日期**：2026-03-03
**範圍**：~8 files (backend 3 + frontend 5), 跨 Application 層 + 前端全棧, 7 commits

**本次相關主題**：Cross-Entity Mutual Exclusion、Token Lifecycle Management、API Key Per-Vendor Grouping、Radio vs Checkbox UX Pattern

### 做得好的地方

- **Model-Level 互斥而非 Provider-Level**：最終設計允許多個 Embedding provider 同時啟用，但全站只能有一個 `is_default=true` 模型。互斥邏輯放在 `UpdateProviderSettingUseCase`，更新 embedding model 時自動清除所有其他 provider 的 `is_default`。比 provider-level 互斥更靈活（可預先啟用多個供應商、設好 API Key，切換只需點 radio）
- **401 攔截器設計**：在 `apiFetch` 統一攔截 401，呼叫 `useAuthStore.getState().logout()` 清除 Zustand persist token。利用 Zustand 的 `getState()` 在非 React 上下文中讀寫 store，不需 hook。這是 Zustand 的最佳實踐——store 可在任意 JS 模組中存取
- **API Key 按供應商合併**：同一 vendor 的 LLM + Embedding 共用一組 API Key，前端 `groupByProvider()` 將 settings 按 `provider_name` 分組，一次更新所有 settings。避免使用者困惑「為什麼同一個供應商要設兩次 Key」
- **Bot 模型下拉分組**：使用 shadcn `SelectGroup` + `SelectLabel` 按供應商分組，不可點選的供應商標題作為視覺分隔，使用者快速定位模型

### 潛在隱憂

- **Embedding model 互斥的 Race Condition**：`UpdateProviderSettingUseCase` 先讀所有 embedding provider 再逐一更新 `is_default=false`，非原子操作。高併發下兩個 admin 同時設定不同模型為 default，可能都成功（`is_default` 出現兩個 true）。→ 建議：考慮資料庫層面的 partial unique index 或 distributed lock → 優先級：低（單 admin 操作場景）
- **API Key 批次更新非事務性**：`handleSave` 對同一供應商的多個 settings 逐一呼叫 `updateMutation.mutate()`，若其中一個失敗、另一個成功，會造成 LLM 有新 Key 但 Embedding 仍是舊 Key。→ 建議：後端提供 batch update endpoint，或前端改用 `Promise.all` + rollback → 優先級：中
- **Radio `name="embedding-active-model"` 全域共享**：HTML radio 用同一個 name 實現跨 Card 互斥，但如果元件被多次渲染（如 StrictMode double render），可能出現意外行為。→ 建議：使用 React state 控制 checked 而非依賴 HTML radio group → 優先級：低（已用 `checked` prop 控制）

### 延伸學習

- **Cross-Aggregate Invariant Enforcement**：當業務規則跨越多個 Aggregate（不同 provider 的 `is_default` 互斥），DDD 推薦用 Domain Service 或 Saga 處理，而非在 Use Case 中直接操作多個 Aggregate。本次在 Use Case 層處理是務實選擇，但若未來規則更複雜，考慮提取 `EmbeddingModelSelectionService`
- **Optimistic UI vs Pessimistic UI**：目前 API Key 更新是 pessimistic（等 API 回應才清空 input）。若改為 optimistic（先清空、失敗再回滾），UX 更流暢但實作更複雜
- 若想深入：搜尋 "DDD cross-aggregate invariants"、"Zustand getState outside React"

---

## Provider Settings 模型 DB 化 + Bot 模型選擇

**來源**：Provider Settings 功能擴充 — 模型 DB 化 + 個別模型啟用 + Bot 模型選擇
**日期**：2026-03-03
**範圍**：~25 files (backend 15 + frontend 10 + tests 6), 跨 DDD 四層 + 前後端全棧

**本次相關主題**：JSON Column Schema Evolution、Registry Pattern、Backward-Compatible Migration、Read-Side Backfill

### 做得好的地方

- **JSON 欄位擴充不改 DB schema**：`provider_settings.models` 已是 JSON 欄位，只需在 JSON 內新增 `is_enabled`、`price`、`description`。Repository 的 `.get()` 預設值確保向後相容，不需 Alembic migration、不需新表。這是 JSON column 的最佳實踐——schema-on-read 的靈活性
- **Registry Pattern 集中模型定義**：`model_registry.py` 作為 single source of truth，`CreateProviderSettingUseCase` 首次建立時從此處填充。前端刪除了 `provider-models.ts` 靜態資料，改從 API 讀取。模型清單變更只需改一處（backend domain）
- **Read-Side Backfill 策略**：Repository `_to_entity()` 檢測空 models 時從 `DEFAULT_MODELS` 回填。這解決了既有 DB 記錄（models=[]）的向後相容問題，不需一次性 migration script。下次使用者 save 時自動持久化到 DB
- **Use Case 職責清晰**：`ListEnabledModelsUseCase` 單獨拉出，只回傳已啟用供應商的已啟用模型，供 Bot 下拉用。避免前端自己做雙層過濾邏輯

### 潛在隱憂

- **Read-Side Backfill 的隱式副作用**：Repository `_to_entity()` 在讀取時注入了 domain 知識（DEFAULT_MODELS），打破了 Repository 作為純 persistence 層的職責。若 DEFAULT_MODELS 內容變更，既有使用者看到的模型清單會突然改變（未經 save）。→ 建議：考慮啟動時一次性 migration 替代 read-side backfill → 優先級：低（目前供應商固定）
- **Bot llm_provider/llm_model 未校驗**：Bot 儲存時不檢查指定的 provider+model 是否真的在 enabled-models 中。使用者理論上可直接 API 呼叫寫入不存在的組合。→ 建議：Application 層加校驗（查 ProviderSettingRepository 確認 enabled） → 優先級：中
- **前端 Select value 格式 `provider:model`**：用冒號分隔 provider 和 model，若 model_id 本身包含冒號會壞掉。→ 建議：改用 JSON 物件或 record index → 優先級：低（目前所有 model_id 無冒號）

### 延伸學習

- **JSON Column Schema Evolution**：NoSQL-in-SQL 模式。JSON 欄位的 schema 演進策略：(1) Schema-on-read + 預設值, (2) Lazy migration（讀取時升級+下次寫入持久化）, (3) 一次性 batch migration。本次用了 (1)+(2) 組合
- **Registry vs Configuration**：Registry Pattern（code-defined defaults）適合穩定、低頻變更的資料。當模型清單需要非工程師管理時，應升級為 Admin CRUD + seed data 模式
- 若想深入：搜尋 "JSON schema evolution patterns PostgreSQL"、Martin Fowler "Registry Pattern"

---

## DeepSeek Provider 集成 + Provider Settings 兩層開關簡化

**來源**：Demo 準備 — 多供應商支援 + 管理介面簡化
**日期**：2026-03-03
**範圍**：~15 files (backend 6 + frontend 7 + tests 4), 跨後端 Domain/Infrastructure/Interfaces + 前端 Settings 全棧

**本次相關主題**：Multi-Provider Selector Pattern、.env Fallback Chain、Pre-defined Card UI Pattern、OpenAI-compatible API 複用

### 做得好的地方

- **OpenAI-compatible API 複用**：DeepSeek API 與 OpenAI SDK 完全相容，只需換 `base_url` + `api_key`。後端完全複用 `OpenAILLMService` 和 `OpenAIEmbeddingService`，零新 Service 類別。dependency-injector 的 `providers.Selector` 配合 config key 路由，乾淨地實現了多供應商切換
- **Dynamic Factory .env Fallback Chain**：`_ENV_KEY_MAP` 將 `provider_name` 映射到 `Settings` 屬性名，DB 無 API Key 時自動從 `.env` 取值。這讓 Provider Settings 頁面不需要填寫 API Key（由運維管理 `.env`），簡化了管理流程又不破壞既有 DB 加密架構
- **Pre-defined Card UI 模式**：前端從 `PROVIDER_MODELS` 靜態定義生成卡片列表，與 DB records 做 match。使用者只需 toggle Switch 啟用/停用，首次啟用時自動 create DB record。比「先新增再管理」的 CRUD 模式直覺得多
- **前端 hardcode 模型清單**：價格、模型名稱、ID 全部寫在 `provider-models.ts`，不從後端 API 拉取。對於 4 家固定供應商的場景，這比動態 API 簡單且零延遲。變更時只需更新前端一個檔案

### 潛在隱憂

- **模型清單與後端不同步風險**：前端 hardcode 的模型清單若與後端 Dynamic Factory 支援的模型不一致，使用者可能選到後端不支援的 model。→ 建議：若供應商數量超過 6 家或模型頻繁變動，改為後端提供 `/api/v1/providers/models` 端點 → 優先級：低（目前 4 家固定）
- **DeepSeek base_url 硬編碼**：`https://api.deepseek.com/v1` 寫在 Container 和 Dynamic Factory 兩處。若 DeepSeek 更換 API endpoint，需改兩處。→ 建議：統一到 `Settings` 的 `deepseek_base_url` 設定 → 優先級：低
- **Provider Settings 無 API Key 時的錯誤提示**：若 `.env` 也沒有對應的 API Key，Dynamic Factory 會拿到空字串，呼叫 LLM 時才會報錯。→ 建議：啟用 provider 時做前置檢查（test-connection），或在 UI 顯示「.env 未設定」警示 → 優先級：中

### 延伸學習

- **Selector Pattern in DI**：dependency-injector 的 `providers.Selector` 類似 Strategy Pattern 的 DI 版本。根據 config value（如 `llm_provider`）動態選擇實作，比 `if/elif` 鏈更具擴展性。新增供應商只需加一行 `deepseek=providers.Factory(...)` 而非修改 switch 邏輯
- **OpenAI-compatible API 生態**：DeepSeek、Groq、Together AI、Fireworks AI 等都提供 OpenAI-compatible endpoint。這意味著只要支援 `base_url` 切換，一個 `OpenAILLMService` 可以覆蓋大量供應商。這是目前 LLM 整合的最佳實踐——優先用 OpenAI SDK 而非各家原生 SDK
- 若想深入：搜尋「OpenAI compatible API providers list」、「dependency-injector Selector provider」、「LiteLLM unified interface」（LiteLLM 是更進階的多供應商統一方案）

---

## Frontend Framework Migration — Next.js 16 → React + Vite SPA

**來源**：技術棧統一（與 payngo-admin-react 對齊）+ 部署成本優化
**日期**：2026-03-02
**範圍**：92 files changed (+1728 / -5393), 跨 Frontend 全棧 + Claude Code 配置

**本次相關主題**：框架遷移策略、SPA vs SSR 架構選型、React Router v6 Layout Routes、靜態部署

### 做得好的地方

- **遷移前分析到位**：先量化「Next.js 使用率」（11/11 頁面 `'use client'`、0 API Routes、0 Server Components 有意義使用），用數據證明遷移合理性，而非憑直覺
- **1:1 路由對映**：Next.js file-based routing 的 11 個頁面全部對映到 React Router v6，使用 `React.lazy()` + `Suspense` 保留 code-splitting 能力，零功能損失
- **Layout Routes 嵌套**：`ProtectedRoute` (auth guard) → `AppShell` (sidebar + header) → `Outlet` 的三層結構，等同 Next.js `(auth)/layout` + `(dashboard)/layout` 的嵌套效果，但更明確
- **測試基礎設施同步更新**：`test-utils.tsx` 加入 `MemoryRouter` wrapper，確保所有使用 `<Link>` 的元件在測試中不報錯。150 個測試全通過，零 regression
- **配置全面清理**：不只改程式碼，連 Claude Code 的 11 個 rules/agents/skills 都同步更新，避免未來 AI 輔助開發時產生過期建議

### 潛在隱憂

- **Client-side routing 的 404 問題** → nginx/CDN 部署時必須設定 fallback to `index.html`（SPA 常見陷阱），否則直接訪問 `/chat` 會 404 → 優先級：中（部署時處理）
- **Bundle 大小未做 analysis** → 目前 1.2MB 含所有 chunks，未來應定期用 `npx vite-bundle-visualizer` 檢查是否有意外大包 → 優先級：低
- **環境變數洩漏風險** → `VITE_*` 變數會被打包到 client bundle 中（與 `NEXT_PUBLIC_*` 行為相同），需確保不放敏感值 → 優先級：低（已有 security rule 覆蓋）

### 延伸學習

- **SPA vs SSR 決策框架**：核心問題是「你的首屏內容是否需要 SEO + 即時可見？」B2B 後台答案永遠是 No → SPA 是正確選擇。Next.js 的 App Router 在純 SPA 場景下是過度工程
- **React Router v6 Layout Routes**：`<Route element={<Layout />}>` + `<Outlet />` 模式是 Next.js nested layouts 的精確等價物，但路由定義集中在一個檔案，可讀性更好
- 若想深入：搜尋「React Router v6 data routers (createBrowserRouter)」— 這是更進階的 loader/action 模式，類似 Remix，但本專案用 TanStack Query 管理資料，不需要

---

## PostgreSQL 連線洩漏修復 — ContextVar Session 生命週期管理

**來源**：E2E 壓力測試中發現的效能退化
**日期**：2026-02-28
**範圍**：1 NEW + 6 MODIFY + 3 test files, 跨 Infrastructure + Container + Main

**本次相關主題**：AsyncSession 生命週期、ContextVar per-request scoping、DI provider delegation、ASGI middleware 選型

### 做得好的地方

- **根因分析到位**：從「API 回應 32 秒」追溯到「27 條 idle in transaction 連線」，再追到 3 個具體洩漏來源（Factory 無 close、Singleton 急切解析、啟動時急切建立），層層遞進不做表面修補
- **ContextVar + Pure ASGI Middleware 組合**：`ContextVar` 天然支援 asyncio 的 per-task 隔離，搭配 pure ASGI middleware（而非 `BaseHTTPMiddleware`），正確處理 SSE StreamingResponse 和 BackgroundTasks 場景。`BaseHTTPMiddleware` 會把 response body 包在背景 thread 中，破壞 SSE 串流
- **dependency-injector `.provider` delegation**：用 `.provider` 屬性傳遞 Factory provider 本身而非解析後的值，讓 Singleton 工廠類別每次呼叫時建立全新 repo。這是 dependency-injector 的正規用法，零 hack
- **零侵入性**：13 個 Repository、所有 Use Case、所有 Router 端點完全不需改動。session 追蹤對業務層完全透明

### 潛在隱憂

- **ContextVar 在非 HTTP scope 下無效**：如果有 background worker（Celery、APScheduler）直接呼叫 Use Case，session 不會被追蹤和清理。目前專案沒有這種場景，但未來若加入需注意 → 建議：為非 HTTP 入口點提供 `async with tracked_session_scope()` context manager → 優先級：低
- **middleware 順序敏感**：`SessionCleanupMiddleware` 必須是最外層（最先 add_middleware = middleware chain 最後執行），才能在所有業務邏輯完成後清理。如果有人在它之前加入新 middleware 且該 middleware 建立 session，那些 session 不會被追蹤 → 建議：在 middleware 註冊處加註釋說明順序約束 → 優先級：中

### 延伸學習

- **SQLAlchemy `autobegin=True` 的隱患**：SQLAlchemy 2.x 預設 `autobegin=True`，第一次 `execute()` 就隱式開啟交易。如果只做 `SELECT` 而不 `close()`，連線會停在「idle in transaction」而非釋放回 pool。這跟「讀操作不需要交易」的直覺相違。解法：要麼每次用完 `close()`（本次做法），要麼設 `autobegin=False` 手動管理交易
- **Pure ASGI vs BaseHTTPMiddleware**：Starlette 的 `BaseHTTPMiddleware` 內部用 `anyio.create_memory_object_stream` 包裝 response body，會在某些場景（SSE、大檔下載）造成問題。Pure ASGI middleware 直接操作 `scope/receive/send`，沒有這層包裝，但寫起來較底層。FastAPI 官方文件也建議效能敏感的 middleware 用 pure ASGI
- 若想深入：搜尋「SQLAlchemy asyncio session lifecycle best practices」、「Starlette BaseHTTPMiddleware limitations streaming」、「Python ContextVar async scoping」

---

## Frontend E2E User Journeys — 雙角色覆蓋全功能

**來源**：E2E 測試強化
**日期**：2026-02-27
**範圍**：~20 files (8 NEW features + 5 NEW steps/pages + 7 MODIFIED POMs/steps), 純前端 E2E framework

**本次相關主題**：E2E Test Architecture, Page Object Model 中文化, Dual-Token Auth Testing, Test Data Seeding Strategy

### 做得好的地方

- **雙角色 Token 驗證策略**：`tenant_access`（系統管理員 via `/auth/login`）和 `user_access`（租戶管理員 via `/auth/user-login`）兩種 JWT 路徑都有 E2E 覆蓋。租戶管理員登入透過 API 取得 token → 注入 Zustand localStorage → reload 頁面，模擬真實的 SPA 認證流程
- **Journey 與 Feature Tests 共存**：journey features 放 `e2e/features/journeys/`，與既有 per-feature tests 互補而非替代。Journey 驗證跨頁面流程，Feature 驗證單頁面功能，各司其職
- **全域 Step 複用**：playwright-bdd 的 step definitions 是全域註冊的，journey tests 大量複用既有 steps（如 `使用者已登入為`, `使用者在知識庫頁面`），僅新增 2 個 step 檔案
- **global-setup 冪等 Seeding**：所有 seed 操作都先檢查「是否已存在」再建立（KB by name, tenant by name, bot by count, user by 400/409 status），多次執行不會產生重複資料

### 潛在隱憂

- **ChatPage.goto() 隱含 bot 選擇邏輯**：`goto()` 現在會自動點擊 "E2E 測試機器人" card。如果 bot 名稱變更或有多個 bot，這個硬編碼名稱可能導致測試不穩定 → 建議：改用 `botCard.first()` 而非 `getByText("E2E 測試機器人")` → 優先級：低
- **FakeLLM 回覆內容不穩定**：J5 的多輪對話步驟（`使用者發送訊息 "我要退貨"` → `應顯示 Agent 回覆`）只驗證「有回覆」不驗證內容。FakeLLM 回傳 `"根據知識庫：{snippet}"`，若 KB 無資料會回傳 `"知識庫中沒有找到相關資訊"`，兩者都會通過測試。這是設計選擇（穩定 > 精確），但團隊需知悉 → 優先級：低
- **Bot management flaky test**：`bot-management.feature` 的「機器人卡片顯示基本資訊」scenario 第一次執行偶爾失敗（card 尚未渲染），retry 後必定通過。可能是 TanStack Query 初次 fetch 的 timing 問題 → 建議：增加 `waitFor` timeout 或 polling → 優先級：低

### 延伸學習

- **Zustand Persist + E2E Token Injection**：Zustand 的 `persist` middleware 將 state 序列化到 `localStorage`。E2E 測試透過 `page.evaluate()` 直接寫入 localStorage key（`auth-storage`），然後 `page.reload()` 觸發 Zustand rehydration。這比模擬 UI 登入流程快得多，且不依賴登入頁面的 DOM 結構
- **playwright-bdd Step 全域性**：與 Cucumber.js 不同，playwright-bdd 的 step definitions 是全域註冊到同一個 `test` fixture。任何 feature file 都能使用任何 step，不需要 import。這帶來高度複用性，但也意味著 step 命名必須全域唯一，否則會衝突
- 若想深入：搜尋「Playwright Page Object Model best practices 2025」、「playwright-bdd global step definitions」、「Zustand persist rehydration testing」

---

## Issue #15 隱憂修復 — Reprocess Task Tracking + Cross-BC JOIN

**來源**：Issue #15 架構筆記標記的隱憂修復
**日期**：2026-02-27
**範圍**：8 files modified, 跨 Domain/Application/Infrastructure/Interfaces 4 層

**本次相關主題**：Background Task 追蹤模式、`safe_background_task` kwargs 陷阱、SQL IN clause vs JOIN 效能、N+1 查詢盤點

### 做得好的地方

- **沿用既有兩階段模式**：Upload 已有 `begin_upload()` → `ProcessDocumentUseCase.execute(task_id)` 的兩階段追蹤。Reprocess 完全複用此模式（`begin_reprocess()` → `execute(doc_id, task_id)`），無新概念引入，維護成本零增加
- **functools.partial 正確解決 kwargs 被吞問題**：`safe_background_task` 的 `**context` 參數會吃掉所有 kwargs。用 `functools.partial` 預先綁定 kwargs 到 callable 中，乾淨且不需修改 `safe_background_task` 簽名
- **JOIN 替代 IN clause 是正確的 DB 優化方向**：`find_chunk_ids_by_kb(kb_id)` 用 `JOIN chunks ON documents WHERE documents.kb_id = :kb_id`，讓 DB 引擎用 index nested loop join，而非應用層先撈 doc_ids 再塞 IN clause。KB 內文件越多，效能差距越大
- **失敗時不再 raise**：背景任務的 exception 本來就不會回傳給 HTTP response，之前的 `raise` 只會被 `safe_background_task` 再次捕捉。現在直接在 Use Case 內處理（update task status → log），語義更清晰

### 潛在隱憂

- **N+1 盤點發現 3 處真正的 N+1**：Bot Repository `find_all_by_tenant()` 每個 bot 各查一次 KB IDs（最嚴重）、Feedback Repository `get_negative_with_context()` 每筆 feedback 查 2 次 message、Conversation Repository `save()` 每個 message 逐筆 lookup → 建議：P0 先修 Bot N+1（影響前端 Bot 管理頁）→ 優先級：中
- ~~**`find_chunk_ids_by_documents()` 已無呼叫者**~~ → **已刪除**（2026-02-27）：被 `find_chunk_ids_by_kb()` 取代，無呼叫者即為重構遺留物，直接移除
- **Reprocess 背景任務無 retry 機制**：失敗後只記錄 `failed` 狀態，使用者需手動重試。若未來需要自動重試可考慮 Celery / ARQ task queue → 優先級：低

### 延伸學習

- **IN clause vs JOIN 的選擇**：IN clause 適合「已知少量 ID 清單」的場景（如 batch get by IDs）；JOIN 適合「由關聯條件篩選」的場景（如 kb_id 對應的所有 chunks）。經驗法則：如果 ID 清單來自另一張表的查詢結果，就應該用 JOIN 讓 DB 一次搞定，而非應用層先撈 ID 再塞 IN
- **Bulk IN Pattern**：當確實需要 IN clause 時（如批次查詢 N 個使用者），應一次收集所有 ID 後發一次 `WHERE id IN (all_ids)` 查詢，再在 Python 端 group by。這是解決 N+1 的標準手段，比 JOIN 簡單但 ID 數量有上限（MySQL ~65535 placeholders、PostgreSQL 無硬限但效能退化）
- 若想深入：搜尋「SQLAlchemy selectinload vs subqueryload」、「PostgreSQL IN clause performance limit」、「Django select_related vs prefetch_related」（概念相同）

---

## Issue #15 — Chunk Quality Monitoring 品質指標 + 回饋關聯

**來源**：E6 延伸 / GitHub Issue #15

**本次相關主題**：Domain Service 純函數設計、Cross-BC Read-Only Aggregation、Quality Score 持久化策略

### 做得好的地方

- **ChunkQualityService 作為純函數 Domain Service**：`calculate(chunks) -> QualityScore` 完全無外部依賴，易測試、可複用。扣分演算法（too_short -0.3, high_variance -0.2, mid_sentence_break -0.2）規則清晰，品質問題以 tuple 記錄便於前端消費
- **Cross-BC 查詢架構合理**：`GetDocumentQualityStatsUseCase` 跨 Knowledge + Conversation BC 做 read-only 聚合，放在 Application 層是正確決策 — 不需要 Domain Event，因為是「查詢時才組裝」而非「即時同步」
- **品質分數持久化到 Document**：避免每次列表渲染都重算，計算在 ProcessDocument 完成時一次性寫入 5 個欄位。Reprocess 時自動重新計算
- **前端品質呈現層次分明**：QualityCell（icon 分 3 級顏色）→ QualityTooltip（hover 顯示建議）→ ChunkPreviewPanel（展開看 chunk 明細）→ ReprocessDialog（參數覆寫重新處理），使用者操作路徑自然
- **11 BDD scenarios + 18 frontend tests 全過**，覆蓋率 82.47%

### 潛在隱憂

- **quality_issues 存為 comma-separated string**：目前 Document.quality_issues 在 DB 是 Text 欄位（逗號分隔），若未來 issue 類型增多或需要結構化查詢，可能需遷移至 JSON 欄位 → 建議：現階段可接受（issue 類型固定 3 種），若超過 5 種考慮改 JSON → 優先級：低
- ~~**Reprocess 無任務追蹤**~~ → **已修復**（2026-02-27）：新增 `begin_reprocess()` + `execute(task_id)` 兩階段追蹤，沿用 Upload 既有模式
- ~~**Cross-BC 查詢 N+1 風險**~~ → **已修復**（2026-02-27）：新增 `find_chunk_ids_by_kb()` 用 JOIN 取代 IN clause

### 延伸學習

- **CQRS (Command Query Responsibility Segregation)**：本次 Cross-BC 查詢本質上是 CQRS 中的 Query 端，如果讀寫模型差異更大，可考慮獨立的 Read Model 或 View Table
- **Composite Quality Scoring**：當前演算法是加權扣分式，若需更複雜的品質模型，可參考 [SonarQube 的 Quality Gate](https://docs.sonarqube.org/latest/user-guide/quality-gates/) 概念 — 多維度 + 門檻 + 歷史趨勢

---

## Issue #9 — API Rate Limiting + User Auth 身份體系

**來源**：Edge Case E7 / GitHub Issue #9

**本次相關主題**：新 Bounded Context 建立、JWT 雙格式向後相容、Sliding Window Counter、Starlette Middleware

### 做得好的地方

- **兩個新 Bounded Context**（`auth`、`ratelimit`）嚴格遵守 DDD 4-Layer：Domain 層純 Python，不依賴框架
- **JWT 向後相容**：根據 `type` 欄位分派，舊 `tenant_access` token 持續運作，零中斷
- **User entity invariant**：`__post_init__` 直接校驗 role-tenant 一致性（system_admin → tenant_id=None；其他角色 → tenant_id required）
- **Graceful Degradation**：Redis 斷線時限流放行 + warning log，不影響正常服務
- **Multi-Layer Rate Limiting**：global → tenant/IP → per-user 三層檢查，最嚴格的 wins
- **19 個 BDD scenarios 全過**，覆蓋率 82%，lint 零錯誤

### 潛在隱憂

- **Middleware 直接依賴 DI Container 實例**（`container.redis_client()` 在 `create_app` 中提前解析）→ 若 Redis 未就緒會影響 app 啟動 → 建議：改為 lazy init 或啟動 probe → 優先級：低
- **Sliding Window Counter 精確度**：`ZADD` 用 `str(now)` 作 member，高併發下同一毫秒可能碰撞 → 改用 `{now}-{uuid}` 格式 → 優先級：中
- **Config Loader DB 查詢**：cache miss 時每次 request 會觸發 DB 查詢（含 null + tenant 兩次）→ 高流量下可能成為瓶頸 → 建議：批次載入 + local LRU cache → 優先級：中
- **bcrypt rounds 寫死 12**：生產環境可能需要調高（但會增加 latency）→ 已透過 config 可配置，但缺乏文件提醒 → 優先級：低

### 延伸學習

- **Token Bucket vs Sliding Window Counter**：兩者各有取捨。Token Bucket 適合突發流量（burst-friendly），Sliding Window Counter 更精確但需要 sorted set 空間。本次選擇 Sliding Window 因為需要精確的「過去 N 秒內請求數」語義
- **API Gateway Rate Limiting**：生產環境通常在 API Gateway（如 Kong, Envoy）層做限流，應用層作為第二道防線。若未來上 K8s，可考慮遷移至 Ingress 層
- **若想深入**：搜尋 "rate limiting algorithms comparison"、"Redis cell module"、"distributed rate limiting patterns"

---

## Issue #8 — Embedding 429 Rate Limit + Adaptive Batch Size

**來源**：Edge Case E1 / GitHub Issue #8
**日期**：2026-02-26
**相關主題**：Retry Pattern、Adaptive Backoff、Rate Limit Resilience

### 做得好的地方

- **Retry-After header 尊重**：讀取 429 Response 的 `Retry-After` header 作為等待時間基準，搭配 `retry_after_multiplier` 設定讓用戶可微調。比固定退避更符合 API provider 的意圖。
- **Adaptive batch size**：遇到 429 後自動將 batch 從 50 → 25 → 10（`min_batch_size`），降低後續觸發 rate limit 的機率。這是 self-healing pattern 的輕量實作。
- **Config 外化**：`retry_after_multiplier`、`min_batch_size` 均為 config 參數，可依不同 provider（OpenAI / Qwen / Google）調整，無需改程式碼。
- **BDD 完整覆蓋**：2 個新 scenario 分別測 Retry-After 等待時間驗證 + batch size 自動縮減，step definition 內 mock `asyncio.sleep` 以精確驗證等待行為。

### 潛在隱憂

- **單一 client 視角**：目前 adaptive batch 只在單次 `embed_texts()` 內有效，重啟後回到初始 batch size。若多個 background task 同時 embedding，各自獨立退避，可能仍觸發 429。 → 可考慮 shared rate limiter（Redis semaphore） → 優先級：低
- **Retry-After 精度**：部分 provider 回傳整數秒，部分回傳 HTTP-date 格式。目前只處理數值型，date 格式會 `float()` 失敗。 → 加 try/except + fallback → 優先級：低
- **pytest-bdd + `unittest.mock.call` 陷阱**：`from unittest.mock import call` 在 module scope 會導致 `scenarios()` 的 `frozenset()` 因 `_Call.__getattr__` 魔法方法而失敗（`unhashable type: '_Call'`）。這是 pytest-bdd 與 mock 的交互 bug。 → 避免在有 `scenarios()` 的模組中 import `call` → 優先級：高（已修復）

### 延伸學習

- **Circuit Breaker Pattern**：當 429 連續觸發超過閾值，應完全停止請求一段時間（open state），而非無限重試。與本次 adaptive batch 互補。
- **Token Bucket / Leaky Bucket**：client-side rate limiting 的經典演算法，可在發送前主動限流，避免 server 回 429。
- **若想深入**：搜尋 "resilience4j rate limiter" 或 Martin Fowler's "Circuit Breaker" pattern。

---

## Issue #7 — Integration Test Deadlock 根因修復

**日期**：2026-02-26 | **範圍**：conftest.py deadlock fix + coverage run 移除 + coverage omit 修正 | **影響**：3 commits, 2 modified files

### 本次相關主題

PostgreSQL pg_terminate_backend 非阻塞語意、Python coverage.py sys.settrace 干擾、asyncpg Event Loop 親和性、測試基礎設施可靠性

### 做得好的地方

- **根因分析徹底**：不止修了表面 deadlock，追蹤到 `pg_terminate_backend()` 的 PostgreSQL 文件（「sends SIGTERM, returns immediately」），理解 dying connection 仍持有鎖。加入 `pg_stat_activity` poll loop（最多 5 秒）確認連線真正關閉後才執行 DDL
- **coverage run + asyncpg 不相容問題正確診斷**：`coverage run` 透過 `sys.settrace()` hook 攔截每一行程式碼執行，這會干擾 asyncpg 的連線生命週期管理（TCP socket 在錯誤時機被 GC 回收），導致 `ConnectionDoesNotExistError`。解法：integration test 永遠用 plain `pytest`，coverage 只量 unit test
- **coverage omit 分層一致**：`repositories/*` 和 `interfaces/*` 由 integration test 覆蓋，不應算入 unit test coverage 分母。加回 omit 後 unit coverage 從 56.87% 回到 82.90%

### 潛在隱憂

| 隱憂 | 建議改善 | 優先級 |
|------|---------|--------|
| Integration test 沒有 coverage 統計 | 若需要完整覆蓋率報告，可用 `pytest-cov` 的 `--cov-append` 只對 unit 啟用 coverage，integration 結果以 scenario pass rate 為準 | 低 |
| `Event loop is closed` GC warning（teardown 階段） | DI Factory sessions 未顯式 close。長期應在 Repository 或 middleware 層加 session lifecycle 管理 | 低（不影響正確性） |
| 38 個 API routes 零 integration test 覆蓋 | 已開 Issue 追蹤，需按優先級分批補齊（Agent/Conversation 為 CRITICAL） | 高 |

### 延伸學習

- **`pg_terminate_backend` vs `pg_cancel_backend`**：terminate 發 SIGTERM（強制關閉，等同 `kill -15`），cancel 發 SIGINT（取消當前查詢但連線保留）。測試 teardown 必須用 terminate，但必須等待 process 真正結束
- **Python tracing hooks 對 async 的影響**：`sys.settrace()` 在每次 Python 函數呼叫/返回時觸發。asyncpg 使用 Cython 擴展（`asyncpg/protocol/protocol.pyx`），tracing hook 可能在 coroutine 切換時插入額外的 Python 幀，擾亂 asyncpg 的 protocol state machine
- **測試 coverage 的哲學**：unit test coverage 量化「邏輯分支覆蓋」，integration test 量化「端點行為覆蓋」。兩者測量不同維度，不應混合在同一個 coverage 報告中。最佳實踐：unit coverage ≥ 80% + integration scenario pass rate 100%
- 若想深入：搜尋「Python sys.settrace asyncio interaction」、「PostgreSQL pg_terminate_backend wait」、「SQLAlchemy NullPool vs QueuePool testing tradeoffs」

---

## Issue #7 — Integration Test 基礎設施建立

**日期**：2026-02-26 | **範圍**：Integration Test infra + 14 BDD scenarios | **影響**：9 new files + 1 modified (pyproject.toml)

### 本次相關主題

Integration Test Infrastructure、asyncpg Event Loop Affinity、pytest Fixture Lifecycle、DI Container Testing、Database Isolation Strategy

### 做得好的地方

- **BDD-first 完整流程**：先寫 3 個 `.feature` 檔（14 scenarios），再寫 step definitions，再寫 conftest infra。Feature 覆蓋 Tenant CRUD（5）+ KB CRUD（5）+ Document CRUD（4），含認證、隔離、錯誤處理
- **DI Container Override 策略正確**：只 override 必要的 4 個 provider（db_session、process_document、vector_store、cache_service），其餘走真實 DI 路徑。這確保了 JWT、Router、UseCase、Repository 全部是真實實作
- **Fresh Event Loop + drop_all/create_all 策略**：每次 `_run()` 建立全新 event loop，避免 asyncpg 跨 loop 問題。每個測試前 drop_all + create_all 重建全部表格，比 TRUNCATE 更健壯（處理 schema corruption）
- **pg_terminate_backend + poll loop 解決 deadlock**：`pg_terminate_backend()` 是非同步的（發送 SIGTERM 後立即返回），dying connection 仍持有鎖。加入 `pg_stat_activity` poll loop 等待連線真正關閉後再執行 DDL，消除 AccessExclusiveLock deadlock

### 潛在隱憂

| 隱憂 | 建議改善 | 優先級 |
|------|---------|--------|
| DI Factory sessions 未顯式 close（依賴 GC cleanup）| 在 Repository 或 middleware 層加 session lifecycle 管理（`async with session_factory() as session:`） | 中 |
| pytest-asyncio 完全停用（`-p no:asyncio`）| 目前所有測試都用 `_run()` 所以安全，但未來若需 async fixtures 需重新啟用 | 低 |
| 每測試 drop_all/create_all 有效能開銷 | 14 scenarios 耗時 ~13s（可接受），若未來 > 50 scenarios 可考慮改回 TRUNCATE + 更精確的連線管理 | 低 |
| Coverage fail_under 暫降至 70 | Integration test 到位後調回 80 | 低 |

### 延伸學習

- **asyncpg Event Loop Affinity**：asyncpg 連線綁定創建時的 event loop。NullPool 確保每次 `engine.begin()` 都建新連線。用 fresh loop per `_run()` call 最安全——每個 loop 只用一次，不存在跨 loop 問題
- **pg_terminate_backend 是非同步操作**：PostgreSQL 文件明確指出此函數「sends a signal」而非「waits for termination」。在測試基礎設施中，必須 poll `pg_stat_activity` 確認 connection count = 0 後才能安全執行 DDL（DROP TABLE 需要 AccessExclusiveLock）
- **Factory vs Scoped Provider 在 DI 測試中的差異**：`providers.Factory` 每次建新實例但不管理生命周期（caller 負責 close）。`providers.Resource` 支援 `init` + `shutdown` lifecycle。若 session 改用 Resource provider，DI 容器能自動管理 session close
- 若想深入：搜尋「pg_terminate_backend async behavior」、「SQLAlchemy NullPool testing」、「pytest fixture scope vs event loop lifecycle」

---

## E6 — Content-Aware Chunking Strategy

**日期**：2026-02-26 | **範圍**：CSV row-based splitting + 策略路由 | **影響**：5 new + 5 modified files

### 本次相關主題

Strategy Pattern、Composite Pattern、Open/Closed Principle、Content-Type Routing、Backward Compatibility

### 做得好的地方

- **Strategy + Composite 雙模式**：`ContentAwareTextSplitterService` 同時實現了 Strategy（按 content_type 選策略）和 Composite（持有多個 `TextSplitterService` 子策略）。新增策略只需 `strategies["text/markdown"] = MarkdownSplitter()`，完全符合 OCP
- **ABC 最小改動（向後相容）**：`TextSplitterService.split()` 只新增一個 `content_type: str = ""` 可選參數。既有 32 個測試零修改全通過，證明 backward compatibility 設計正確
- **DI Container Selector 三檔模式**：`chunk_strategy` 支援 `auto`（ContentAware router）/ `recursive`（直接 Recursive）/ `csv_row`（直接 CSV）。生產用 auto，測試或 debug 可切換為特定策略
- **CSV Header 保留**：每個 chunk 前自動加上 CSV header 行，LLM 能理解欄位含義。這是業界 RAG CSV 處理的標準做法（Unstructured.io、LlamaIndex 皆如此）
- **Rich Metadata**：CSV chunks 帶 `row_start`/`row_end`，未來可實現「引用第 3-7 行」的精準 citation

### 潛在隱憂

| 隱憂 | 建議改善 | 優先級 |
|------|---------|--------|
| CSV splitter 用 `\n` 分行，若 CSV 欄位內含換行（RFC 4180 quoted field）會誤切 | 若遇到此需求，改用 `csv.reader()` 解析後再分塊 | 低 |
| `_data_row_index` 用 `is` 比較物件身份而非 `==`，因 rows 來自同一 list 所以安全，但重構時可能意外複製字串 | 改用 enumerate + index tracking 替代 identity comparison | 低 |
| RecursiveTextSplitter 的中文分隔符（。！？；）會在標點後斷開，若標點出現在引號/括號內可能不理想 | 監控實際分塊品質，必要時自訂 `is_separator_regex=True` + lookahead | 低 |

### 延伸學習

- **Chunking 對 RAG 品質的影響**：分塊策略直接影響檢索召回率。固定字元切割會破壞語義邊界（mid-sentence split），導致 embedding 品質下降。Content-aware splitting（按行、按段落、按 heading）能保留語義完整性，是 RAG pipeline 最容易忽視但影響最大的環節
- **Semantic Chunking**：進階做法是計算相鄰句子的 embedding 相似度，當相似度驟降時切割。優點是語義邊界最精準，缺點是需要額外 embedding 呼叫（成本和延遲加倍）。適合對檢索品質要求極高的場景
- 若想深入：搜尋「LangChain SemanticChunker」、「LlamaIndex SentenceWindowNodeParser」、Greg Kamradt 的「5 Levels of Text Splitting」影片

---

## E5 — Redis Cache 統一遷移

**日期**：2026-02-26 | **範圍**：5 個快取遷移至 Redis | **影響**：10 new + 10 modified files

### 本次相關主題

CacheService Abstraction、Graceful Degradation、Encryption at Rest、Strategy Pattern for Cache Backend

### 做得好的地方

- **Domain-level ABC（`CacheService`）放在 `domain/shared/`**：遵循 DDD 依賴方向——Application/Infrastructure 層依賴 Domain 介面，Redis 實作放 Infrastructure。跨 Bounded Context 的 Bot、Feedback、Summary、Factory 都能共用同一介面
- **靜默降級設計（Graceful Degradation）**：`RedisCacheService` 所有操作 try/except `RedisError` → log warning + 回傳 None/no-op。Redis 斷線時等同「無快取」模式，業務邏輯完全不受影響
- **InMemoryCacheService 測試替身**：200 個 Unit Test 全用 InMemory 實作，無需 Docker Redis。測試速度 1.88s 全通過
- **Factory 快取加密**：Dynamic LLM/Embedding Factory 的 config 含 API key，存 Redis 前經 `EncryptionService.encrypt()`（AES-256-GCM）加密，讀取時解密。複用既有加密基礎設施，零新增加密邏輯
- **Optional 注入模式**：所有 consumer 的 `cache_service` 參數都是 `CacheService | None = None`，保持向後相容。無 Redis 時自動降級為無快取模式

### 潛在隱憂

| 隱憂 | 建議改善 | 狀態 |
|------|---------|------|
| ~~無 cache invalidation~~ | Update/Delete Use Case 已加 `cache.delete(key)` | **已解決** |
| ~~InMemoryCacheService TTL=0 語義模糊~~ | `set(ttl<=0)` 直接不存，語義明確 | **已解決** |
| Redis `from_url()` 預設已帶 ConnectionPool (max=10) | 多 worker 時調 `max_connections`，部署 prod 再處理 | **不適用**（現階段） |
| Factory 快取 key 是 `llm_config:default`（單一 key） | 所有租戶共用系統級 API key，單 key 設計正確 | **不適用** |

### 延伸學習

- **Cache-Aside Pattern**：本次所有快取都採用 Cache-Aside（Lazy Loading）——先查 cache，miss 時查 DB/計算，再寫 cache。優點是簡單、只快取被請求的資料。缺點是首次請求必定 miss（cold start）。若要預熱可考慮 Write-Through 或 Read-Through 模式
- **Encryption at Rest for Cache**：即使 Redis 部署在 VPC 內，明文儲存 API key 仍有風險（Redis 無原生加密、RDB/AOF 備份可能洩漏）。AES-256-GCM 加密 + 隨機 nonce 確保每次加密結果不同，防止 pattern analysis
- 若想深入：搜尋「Redis security best practices」、「Cache-Aside vs Read-Through vs Write-Behind」、Martin Fowler 的「Two Hard Things」（Cache Invalidation）

---

## E4 — EventBus 死代碼移除 + Redis Cache 規劃

**日期**：2026-02-26 | **範圍**：死代碼清理 + 技術債規劃 | **影響**：8 files, 257 deletions

### 本次相關主題

Dead Code Elimination、YAGNI 原則、Cache 策略演進（in-memory → Redis）

### 做得好的地方

- **零風險移除策略**：先用 `grep` 確認 `InMemoryEventBus` / `EventBus` / `DomainEvent` 在所有 Use Case、Repository、Router、LangGraph agent 中零引用，再刪除。結果 192 scenarios 全通過，無意外破損
- **DDD 分層清理徹底**：Domain 層（events.py）→ Infrastructure 層（in_memory_event_bus.py）→ Container DI → BDD Feature + Steps 全鏈移除，未留殘餘
- **技術債透明化**：將 5 個散落的 in-memory cache 整理成 E5 Sprint 計畫寫入 SPRINT_TODOLIST，附帶現況 → 遷移目標對照表，讓未來接手的人能快速理解背景

### 潛在隱憂

| 隱憂 | 建議改善 | 優先級 |
|------|---------|--------|
| EventBus 被移除意味著未來若要引入 Domain Events 需重新設計 | 在 `docs/` 留一份 ADR 記錄「為何移除」和「何時該重新引入」 | 低 |
| E5 Redis 遷移需要新增 infra 依賴（redis.asyncio）+ Container 改動較大 | 建議 E5.1 先做 ABC + 單元測試，再逐個 Use Case 遷移 | 中 |
| 移除後 `domain/shared/` 目錄可能只剩 exceptions.py，目錄結構是否還合理 | 若 shared/ 只剩 1-2 個檔案可考慮扁平化，但不急 | 低 |

### 延伸學習

- **YAGNI（You Aren't Gonna Need It）**：EventBus 是 S7P1 基於「未來跨聚合通訊需要」的預設計，但 5 個 Sprint 後仍未被任何業務邏輯使用。這是典型的 speculative generality 反模式。教訓：基礎設施元件應在**第一個真實使用場景出現時**才引入，而非「以防萬一」預建
- **Dead Code 的隱性成本**：死代碼不只占空間，它會誤導閱讀者以為系統有 event-driven 能力、增加認知負擔、在重構時產生虛假依賴。定期盤點 + 果斷移除是保持 codebase 健康的必要衛生習慣
- **Cache 策略演進路徑**：`dict` TTL（E3） → `TTLCache[K,V]` 通用類 → Redis（E5）。每一步的觸發條件：3+ Use Case 需要 cache 時抽工具類；需要多 Worker 一致性時上 Redis。不要跳級

#### 思考題

> EventBus 被移除了，但「跨聚合通訊」的需求未來可能會回來（例如：Bot 設定更新時通知所有 cache 失效）。到時候你會選擇：
> (A) 重新引入 in-process EventBus（同步 / 單 Worker）
> (B) 用 Redis Pub/Sub 做 cross-worker event bus
> (C) 用 PostgreSQL LISTEN/NOTIFY
> (D) 直接在 Use Case 中呼叫需要通知的 Service
>
> 各方案在什麼規模下最合適？哪個最符合現有架構的 DDD 分層原則？

---

## E3 — 邊緣問題批次修復（Edge Case Batch Fix）

**日期**：2026-02-26 | **範圍**：E3-E11（8 fixes） | **影響**：~30 files, 跨前後端 + 跨 4 DDD 層

### 使用的設計模式

| 模式 | 用在哪裡 | 為什麼選這個 |
|------|---------|-------------|
| Decorator / Wrapper | `safe_background_task` 包裝 FastAPI BackgroundTask | 不修改原始 coroutine，只加一層 try/except + logging |
| TTL Cache (Application-level) | Bot 查詢快取 + 回饋統計快取 | 比 Redis 輕量，Use Case 層控制，不引入新基礎設施依賴 |
| Upsert Pattern | 回饋「改變心意」| find existing → update vs create，比 DELETE+INSERT 更安全 |
| Server-side Pagination | 分析查詢 offset/limit/total | 資料量大時避免一次載入全部，前端只拿一頁 |

### 做得好的地方

- **批次修復策略得當**：8 個邊緣問題依依賴鏈排序（E3→E5→E4→E8→E6→E9→E10+E11），每個子任務完成後全量測試確認無回歸
- **DDD 分層一致**：快取放 Application 層（Use Case 控制），不污染 Domain 或 Infrastructure
- **簽名驗證時序修正（E5）是真正的安全改善**：原本 router 先 JSON parse 再驗簽，攻擊者可用 malformed JSON 繞過驗簽直接觸發 500。修正後先驗簽再 parse，符合「fail fast on untrusted input」原則
- **Upsert 改為 update 而非 delete+create**：保留原始 `created_at` 和 `id`，避免外鍵或引用斷裂
- **前後端分頁協調**：Backend 回傳 `total` + Frontend 用 `page` state 控制 `offset`，query key 含 pagination 避免 stale cache

### 潛在隱憂

| 隱憂 | 建議改善 | 優先級 |
|------|---------|--------|
| Application-level TTL cache 是 per-instance — 多 worker 部署時各 worker 快取不同步 | 若流量大到需多 worker，改用 Redis TTL cache | 低（目前單 worker 足夠） |
| `safe_background_task` 只是 try/except 止血 — 缺乏 request ID correlation、structured context | E3.5 Sprint 建立完整 logging 基礎設施（error correlation + alerting） | 中 |
| PII regex 仍有漏洞 — 地址、護照號、信用卡非標準格式（空格分隔 4444 3333 2222 1111）可能遺漏 | 引入 NER library（如 Microsoft Presidio）做深度遮蔽 | 低 |
| `execute_for_bot` 簽名改為 3 args，既有的 4-arg 呼叫端若有未測到的都會 break | 考慮 keyword-only args 避免位置參數斷裂 | 低（已有 BDD 覆蓋） |
| offset-based pagination 在高併發寫入時可能跳頁或重複 | 未來資料量大時改 cursor-based（`created_at` + `id` 複合 cursor） | 低 |

### 延伸學習

- **Decorator Pattern vs Middleware**：`safe_background_task` 是函式級 Decorator，適合少量調用點。若全系統都需要，應升級為 FastAPI Middleware 或 BackgroundTask 全域 wrapper（E3.5 目標）
- **TTL Cache 的 Thundering Herd 問題**：多個請求同時發現快取過期，全部打 DB。解法：probabilistic early expiration（提前隨機過期）或 lock-based cache refresh。目前規模不需要，但 10x 流量後會出現
- **Signature-First 原則**：Webhook 安全的黃金法則是「先驗簽、再處理」，類似 JWT 的「先驗 token、再讀 payload」。任何處理 untrusted input 的管線都應遵循這個原則

#### 思考題

> 目前 Bot cache 和 FeedbackStats cache 各自在 Use Case 中維護獨立的 `dict` 快取。如果未來有 10 個 Use Case 都需要 TTL 快取，你會：
> (A) 每個 Use Case 各自維護（現在的做法）
> (B) 抽取一個通用的 `TTLCache[K, V]` 工具類
> (C) 引入 Redis 統一快取層
>
> 各方案的 trade-off 是什麼？在什麼規模下你會從 A 升級到 B 再到 C？

---

## E2 完整版 — 企業級回饋分析系統

**日期**：2026-02-26 | **範圍**：E2.5-E2.9 | **影響**：62 files, 3605 insertions

### 使用的設計模式

| 模式 | 用在哪裡 | 為什麼選這個 |
|------|---------|-------------|
| Repository Pattern | 分析查詢（trend/issues/quality/cost）| 將複雜 SQL 封裝在 Infrastructure，Application 層只呼叫介面 |
| Strategy Pattern | PII 遮蔽（`mask_pii_in_text`）| 遮蔽邏輯可替換（regex → NER），不影響匯出 Use Case |
| Proxy Pattern | `execute_stream()` 計時 + metadata 捕獲 | 在不修改 Agent pipeline 的前提下攔截 latency 和 sources |
| Value Object | `DailyFeedbackStat`, `TagCount`, `ModelCostStat` | 分析結果是不可變的查詢快照，適合 frozen dataclass |

### 做得好的地方

- **DDD 分層乾淨**：分析 VO 在 Domain、Use Case 在 Application、SQL 在 Infrastructure、API Schema 在 Interfaces，各層職責清晰
- **既有架構零改動**：`SendMessageUseCase` 只加了計時邏輯，不影響原有 Agent pipeline
- **前後端 type 對齊**：Backend Pydantic schema ↔ Frontend TypeScript interface 一一對應
- **測試覆蓋充分**：18 個 BDD scenarios + 16 個前端元件測試，全量 182+117 通過

### 潛在隱憂

| 隱憂 | 建議改善 | 優先級 |
|------|---------|--------|
| 分析查詢無分頁 — `get_negative_with_context` 只有 limit | 加 cursor-based pagination（`created_at` + `id` 複合游標）| 中 |
| Recharts 200KB bundle 全頁面載入 | `next/dynamic(() => import('./chart'), { ssr: false })` 動態載入 | 低 |
| PII regex 遮蔽不完整 — 地址、身分證字號未涵蓋 | 引入 NER library（如 presidio）或自定義 pattern 擴充 | 低 |
| `retrieved_chunks` 存為 JSON Text 欄位 | 大量 chunks 時查詢效能差；未來可改為 JSONB（PostgreSQL）| 低 |

### 延伸學習

- **CQRS（Command Query Responsibility Segregation）**：本次新增的 4 個分析 Use Case 天然是 Query Side，未來可以獨立成 Read Model 提升查詢效能
- **Materialized View**：`get_daily_trend` 的 GROUP BY DATE 在資料量大時可以用 PostgreSQL materialized view 預計算
- **Event Sourcing**：回饋不支援修改（E8 邊緣問題）若改為 Event Sourcing，每次操作都是一個 event，天然支持修改歷程

---

## E2 MVP — 回饋收集 + Web/LINE 雙通路

**日期**：2026-02-25 | **範圍**：E2.1-E2.4 | **影響**：39 files, 1604 insertions

### 使用的設計模式

| 模式 | 用在哪裡 |
|------|---------|
| Entity + Value Object | `Feedback` Entity, `Rating` / `Channel` / `FeedbackId` VOs |
| Repository Pattern | `FeedbackRepository` ABC → `SQLAlchemyFeedbackRepository` |
| Command Pattern | `SubmitFeedbackCommand` 封裝提交參數 |
| Optimistic Update | 前端 `useSubmitFeedback` — mutate 前先更新 UI，失敗才 rollback |

### 做得好的地方

- **雙通路共用 Domain**：Web FeedbackButtons 和 LINE Postback 都走同一個 `SubmitFeedbackUseCase`
- **防重複機制**：DB UNIQUE constraint on `message_id` 擋住重複回饋
- **前端 Optimistic UI**：點擊後立即回饋視覺反應，提升使用體驗

### 潛在隱憂

| 隱憂 | 建議 | 優先級 |
|------|------|--------|
| 不支援修改回饋（E8）| 改 upsert 邏輯 | 低 |
| 無 rate limiting（E7）| 加 per-tenant 限流 | 中 |
| 統計查詢無快取（E6）| materialized view 或 Redis 快取 | 低 |

### 延伸學習

- **Postback vs Webhook**：LINE Messaging API 的 Postback 是 client-initiated event，與 webhook 的 server-push 不同。Postback 的 data 限制 300 字元，格式設計要精簡
- **Optimistic Update 的 rollback 策略**：TanStack Query 的 `onMutate` / `onError` 搭配是經典的 optimistic update 範例，進階可搭配 `cancelQueries` 避免 stale data 覆蓋

---

## E1.5 — LINE Webhook 多租戶

**日期**：2026-02-24 | **範圍**：E1.5.1-E1.5.2 | **影響**：11 files, 577 insertions

### 使用的設計模式

| 模式 | 用在哪裡 |
|------|---------|
| Abstract Factory | `LineMessagingServiceFactory` — 根據 Bot 動態建立 LINE service 實例 |
| Backward Compatibility | `execute()` 保留舊簽名，新增 `execute_for_bot()` 方法 |

### 潛在隱憂

| 隱憂 | 建議 | 優先級 |
|------|------|--------|
| BackgroundTask 靜默失敗（E3）| structured logging + error notification | 中 |
| 無 Bot 查詢快取（E4）| 短 TTL in-memory cache | 低 |
| 驗簽時序問題（E5）| 先驗簽再解析 JSON | 低 |

### 延伸學習

- **Abstract Factory vs Factory Method**：本次用 Abstract Factory 因為需要根據不同 Bot config 建立不同的 service 實例（不同 channel_secret / access_token）
- **Background Task 可觀測性**：FastAPI BackgroundTasks 的例外不會傳回 HTTP response，正式環境必須有 structured logging + alerting

---

## E1 — System Provider Settings DB 化

**日期**：2026-02-23 | **範圍**：E1.1-E1.6 | **影響**：46 files, 2667 insertions

### 使用的設計模式

| 模式 | 用在哪裡 |
|------|---------|
| Dynamic Proxy | `DynamicLLMServiceProxy` — 每次呼叫時從 DB 載入最新設定 |
| Factory Pattern | `DynamicLLMServiceFactory` — 根據 DB config 動態建立 service |
| Fallback Chain | DB 設定 → .env fallback → error |
| Encryption Service | AES-256-GCM 加密 API Key |

### 延伸學習

- **Dynamic Proxy 的效能陷阱**：每次 LLM 呼叫都查 DB 載入設定，高併發時需加 TTL 快取
- **加密金鑰管理**：master key 仍在 .env，正式環境應用 KMS（AWS KMS / GCP Cloud KMS）

---

## E0 — Tool 清理 + Multi-Deploy

**日期**：2026-02-22 | **範圍**：E0.1-E0.6 | **影響**：22 files 刪除, 20+ files 編輯

### 延伸學習

- **大規模刪除的安全策略**：先確認測試覆蓋 → 刪除程式碼 → 跑全量測試 → 確認無 import error
- **Multi-Deploy 模式**：`enabled_modules` CSV 設定讓同一 codebase 部署為不同服務（API / WebSocket / Webhook），是 monolith → 微服務的過渡策略

---

## S7 — Multi-Agent 2-Tier + Bot Management

**日期**：2026-02-19 | **範圍**：7.0-7.22

### 使用的設計模式

| 模式 | 用在哪裡 |
|------|---------|
| Supervisor Pattern | `MetaSupervisorService` → `TeamSupervisor` → `AgentWorker` 三層調度 |
| ~~Domain Events~~ | ~~`OrderRefunded`, `NegativeSentimentDetected` — 跨聚合通訊~~ — 已在 E3 後清理移除（零使用） |
| State Machine | `RefundStep` enum 驅動多步驟工作流 |
| Aggregate Root | `Bot` 聚合管理 KB 綁定 + LLM 參數 + 工具選擇 |

### 延伸學習

- **Supervisor Hierarchy**：Meta → Team → Worker 的三層架構類似 Erlang/OTP 的 supervision tree
- **State Machine 持久化**：`refund_step` 存在 conversation metadata 中，跨請求保持狀態。進階可用 Temporal / Durable Functions

---

## S6 — Agentic 工作流 + 多輪對話

**日期**：2026-02-15 | **範圍**：6.1-6.7

### 延伸學習

- **對話持久化的 N+1 問題**：`find_by_id` 載入 Conversation + Messages 需注意 eager loading
- **Agent 自我反思**：回答品質自動把關是 Chain-of-Thought 的應用，但會增加 latency。可設定閾值只對低品質回答觸發

---

## S5 — 前端 MVP + LINE Bot

**日期**：2026-02-12 | **範圍**：5.1-5.10

### 延伸學習

- **SSE Streaming 的錯誤處理**：`ReadableStream` 在連線中斷時不會觸發 error event，需要 heartbeat 或 timeout 機制
- **Zustand + TanStack Query 分工**：Zustand 管 client state（UI 狀態），TanStack Query 管 server state（API 資料），避免混用

---

## S4 — AI Agent 框架

**日期**：2026-02-08 | **範圍**：4.1-4.7

### 延伸學習

- **LangGraph StateGraph**：router → tool → respond 的三步圖結構，每個節點是一個 function，state 在節點間傳遞
- **Tool Selection 策略**：關鍵字路由（FakeAgent）vs LLM 路由（LangGraph），前者快但脆弱，後者慢但泛化

---

## Blog 素材提取指南

> 以下是從本 journal 可以提取的 blog 主題建議：

### 架構系列
1. **DDD 4-Layer 在 Python FastAPI 的實踐** — 從 S1-S4 的 Domain/Application/Infrastructure/Interfaces 分層經驗
2. **從 Monolith 到 Multi-Deploy** — E0 的模組化部署策略
3. **Dynamic Proxy Pattern 實現 Provider 熱切換** — E1 的 DB 化設定架構

### AI/RAG 系列
4. **建構 Agentic RAG Pipeline** — S3-S4 的 RAG + Agent 整合
5. **Multi-Agent Supervisor 架構設計** — S7 的三層 Supervisor 模式
6. **從 thumbs up/down 到企業級回饋分析** — E2 的完整回饋系統演進

### 前端系列
7. **Next.js 15 + shadcn/ui + TanStack Query 最佳實踐** — S5 的前端架構
8. **BDD-First 開發在全端專案的應用** — pytest-bdd + playwright-bdd 經驗分享

### 整合系列
9. **LINE Bot × AI Agent 整合實戰** — S5.7 + E1.5 的多租戶 webhook 架構
10. **測試金字塔在 DDD 專案的落地** — 182 backend + 117 frontend tests 的測試策略
