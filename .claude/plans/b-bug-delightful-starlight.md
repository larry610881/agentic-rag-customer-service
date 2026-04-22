# Plan: S-KB-Studio.1 — 自建 KB Studio（RAGFlow UX，shadcn 實作）

> 取代 S-Pricing.1（已 ship commit `3e2173a` + `acdf0f0`）。落地 2026-04-22 凌晨兩個 Plan agent 的 KB Studio 提案（session `c23d5bd2` 對話 index 3239/3244），2026-04-22 晚上 Phase 1 exploration 後修正假設。
>
> **Day 0 hotfix 已 ship**：
> - `660008a` — Milvus `tenant_id` / `document_id` scalar index `""` → `INVERTED`
> - `1c773d9` — 一次性 rebuild script
> - `54d3016` — plan 同步 rebuild 完成狀態
> - Local (2 coll) + dev-vm (6 coll 含 conv_summaries) 都已跑過 rebuild script，目前全部 INVERTED
>
> **GitHub Issue**：待建（Stage 2 開始前建）
> **合併範圍**：Phase 1 (6d) + Phase 2 (6d) 合成單一 sprint，扣掉已完成的 O13 + O14 實際 **~9-10d**

---

## Context

### 為何現在做

1. **RAG 品質除錯沒有工具** — admin 只能 upload/delete 整份文件。chunk 分類不對、context_text 不準、retrieval 差時無法 inline 修正，只能重傳整文（成本 = chunk 數 × embedding 費）
2. **Auto-Classification 已跑但結果是黑盒** — 沒 UI 可改分類名、合併、強制重指派
3. **無 Retrieval Playground** — 上線前沒工具驗「使用者問 X 會檢索到 Y」
4. **Milvus 基礎設施沒可視化** — collection row count / index / memory 狀態全要 SSH 進 VM 才看得到
5. Milvus `tenant_id` scalar index 雪崩風險 **✅ 已解**（Day 0 hotfix）

### 路線決策（已對齊）

**自建 KB Studio，不用 RAGFlow**。關鍵原因（原提案路線 A/C 的致命問題）：
- 資料模型不相容（RAGFlow 自有 Postgres schema vs 我們 MySQL + DDD 4-layer + 17 use cases）
- 租戶模型不相容（RAGFlow tenant = 個人空間，沒 `tenant_id` row-level filter → 破壞隔離）
- Auto-Classification / Contextual Retrieval / Conv Summary 要廢重接

**參考 RAGFlow UX 哲學**：左欄樹狀 / 右欄 detail tabs / chunk inline edit / retrieval test panel，元件用 shadcn 自刻。

### 依賴決策（Phase 1 探索後敲定）

- **虛擬滾動**：`@tanstack/react-virtual`（跟既有 `@tanstack/react-query` 同生態）
- **Drag-and-drop**：HTML5 native（`onDragStart` / `onDrop`，零依賴；chunk 量小足夠用）

### 成功條件

- Admin 進 `/admin/kb-studio/{kbId}` 看到 7 tabs 全正常
- Chunks tab inline 編輯 → debounce 1s autosave → arq enqueue reembed → Milvus upsert
- Retrieval Playground：query → top-K + score + 顯示 filter expression
- Categories tab：CRUD + HTML5 drag reassign
- Milvus Dashboard：collection / row count / index type（應全顯 INVERTED）
- `tenant_admin` 訪問別租戶 `kbId` → 回 404 防枚舉
- 單 chunk re-embed 省 > 80% embedding token（vs 整文 reprocess）
- 全量測試綠 + 覆蓋率不降

---

## Design Decisions

1. **自建，不引入 RAGFlow**（見 Context）
2. **廢 `admin-kb-detail.tsx`**，內容遷入 KB Studio Overview tab，舊 route redirect
3. **Phase 1+2 合併**（~9-10d，已扣除 Day 0 完成項）
4. **Conv Summary 獨立 sidebar 項**，不塞 KB Studio；但 Playground 加 toggle「也搜尋對話摘要」做 cross-search
5. **單 chunk re-embed 走 arq job**（`reembed_chunk`），不走 7 步 pipeline
6. **Inline edit 用 textarea + debounce 1s autosave**（不用 contenteditable 避免格式污染）
7. **Chunk list 用 `@tanstack/react-virtual`**（不等到痛才加）
8. **Categories drag 用 HTML5 native**（零依賴）
9. **Tenant boundary 紅線**：所有 chunk/category endpoint 第一步驗 `chunk→doc→kb→tenant_id == JWT.tenant_id`，URL 不屬於 caller → 回 404 不 403

---

## Phase 1 探索後的假設修正

| 原假設 | 實際 | 影響 plan |
|---|---|---|
| ChunkCategoryRouter 已有 3 routes | ✅ `knowledge_base_router.py:213-309`（prefix `/knowledge-bases/{kb_id}/categories`） | 新增 endpoint 也放這個 router，不另建 |
| DocumentRepository 沒有 chunk 方法 | ⚠️ 已有多個 document-level 方法，但 **確實缺** 5 個 KB-level / single-chunk 方法 | 新增範圍縮小為 5 個方法，照 plan |
| MilvusVectorStore 缺 5 方法 | ✅ 確認缺（list_collections / get_stats / update_payload / count_by_filter / upsert_single） | 照 plan |
| `retrieve()` 已存在可重用 | ✅ `query_rag_use_case.py:199`，已帶 tenant_id filter 與 score | Playground 不需新 use case，加 DTO 曝露 filter_expr 即可 |
| arq `_new_container()` 模式 | ✅ `worker.py:27-30`，每個 job 起新 container | 照抄 pattern 加 `reembed_chunk` |
| Tenant boundary 有既有 pattern | ⚠️ 有 `get_current_tenant` 但多數 use case **沒做** explicit `kb.tenant_id == tenant.tenant_id` chain check | Plan 要補「在 use case 第一行驗 chain」的強制紅線 |
| `react-virtuoso` 已裝 | ❌ 沒裝 | 改裝 `@tanstack/react-virtual` |
| drag-drop lib 已裝 | ❌ 沒裝 | 用 HTML5 native |
| `category-list.tsx` / `chunk-preview-panel.tsx` 可重用 | ✅ 可重用，但要抽 `<ChunkCard mode="view|edit|compact">` 共用 | 原 plan 正確 |

---

## 資料模型 / Migration

### 不需要新表

本 sprint 讀寫既有 `chunks` + `chunk_categories` + Milvus + 新 endpoint，不新建 DB 表。

### ORM 層輕微調整

- `ChunkModel` 確認有 `updated_at` 自動更新欄位（給 inline edit 排序用）
- `ChunkCategoryModel` 確認 cascade 行為（刪 category 時 chunks 的 category_id 設 NULL）

---

## DDD 檔案落點

### 修改（backend）

| 檔案 | 變更 |
|------|------|
| `apps/backend/src/infrastructure/milvus/milvus_vector_store.py` | 加 5 方法：`list_collections`, `get_collection_stats(name)`, `update_payload`, `count_by_filter`, `upsert_single` — 全部 `asyncio.to_thread()` 包 |
| `apps/backend/src/domain/rag/services.py` (VectorStore interface) | 加對應 5 抽象方法 |
| `apps/backend/src/domain/knowledge/repository.py` | 加 5 方法：`update_chunk(chunk_id, content, context_text)`, `find_chunk_by_id`, `find_chunks_by_kb_paginated`, `count_chunks_by_kb`, `delete_chunk` |
| `apps/backend/src/domain/knowledge/entity.py` | `Chunk` 確認 `updated_at` + `category_id` 可變性 |
| `apps/backend/src/domain/knowledge/repository.py`（ChunkCategoryRepository section） | 加 `delete_by_id`, `assign_chunks(cat_id, chunk_ids)` |
| `apps/backend/src/infrastructure/db/repositories/document_repository.py` | 實作上述 5 方法 |
| `apps/backend/src/infrastructure/db/repositories/chunk_category_repository.py` | 實作 delete_by_id + assign_chunks |
| `apps/backend/src/application/rag/query_rag_use_case.py` | `RetrieveResult` dataclass 加 `filter_expr: str` 欄位（讓 playground 看到 debug info） |
| `apps/backend/src/container.py` | 註冊 12 新 use cases + wiring 加 3 新 router |
| `apps/backend/src/main.py` | include 3 新 router（admin_chunk / admin_milvus / admin_conv_summary） |
| `apps/backend/src/worker.py` | 加 `reembed_chunk` job + 註冊到 `jobs` tuple |
| `apps/backend/src/interfaces/api/knowledge_base_router.py` | `/categories` 補 POST / DELETE / assign-chunks 3 endpoints（延伸 line 213 附近） |
| `apps/frontend/src/App.tsx` | 加 3 route：`ADMIN_KB_STUDIO` (`:kbId`), `ADMIN_MILVUS`, `ADMIN_CONV_SUMMARY`；舊 `admin-kb-detail` redirect 到 `kb-studio?tab=overview` |
| `apps/frontend/src/routes/paths.ts` | 加 3 const + 棄用 `ADMIN_KB_DETAIL` 標記（保留跳轉 3 sprint 後刪）|
| `apps/frontend/src/components/layout/sidebar.tsx` | `systemAdminItems` 加 3 項（icon：`Library` / `Database` / `MessagesSquare`）|
| `apps/frontend/src/lib/api-endpoints.ts` | 加 `adminChunks`, `adminMilvus`, `adminConvSummary` namespace |
| `apps/frontend/src/hooks/queries/keys.ts` | 加對應 query keys |
| `apps/frontend/package.json` | `npm add @tanstack/react-virtual` |

### 新建（backend）

| 檔案 | 職責 |
|------|------|
| `apps/backend/src/application/knowledge/update_chunk_use_case.py` | 驗 `chunk→doc→kb→tenant`（強制紅線）→ DB update → enqueue `reembed_chunk` |
| `apps/backend/src/application/knowledge/reembed_chunk_use_case.py` | 單 chunk embedding → Milvus upsert_single → RecordUsageUseCase（type=`embedding`） |
| `apps/backend/src/application/knowledge/delete_chunk_use_case.py` | DB delete + Milvus delete + 失敗 log（retry 留後續 hotfix） |
| `apps/backend/src/application/knowledge/list_kb_chunks_use_case.py` | 分頁 + category filter |
| `apps/backend/src/application/knowledge/test_retrieval_use_case.py` | 薄 wrapper：呼叫 `QueryRAGUseCase.retrieve()`，回 results + filter_expr + 可選 conv_summary cross-search |
| `apps/backend/src/application/knowledge/get_kb_quality_summary_use_case.py` | KB-level quality 聚合 |
| `apps/backend/src/application/chunk_category/create_category_use_case.py` | |
| `apps/backend/src/application/chunk_category/delete_category_use_case.py` | 級聯 chunks 設 NULL |
| `apps/backend/src/application/chunk_category/assign_chunks_use_case.py` | 批次指派 |
| `apps/backend/src/application/milvus/list_collections_use_case.py` | tenant admin 過濾；platform admin 看全部 |
| `apps/backend/src/application/milvus/get_collection_stats_use_case.py` | |
| `apps/backend/src/application/milvus/rebuild_index_use_case.py` | `/collections/{name}/rebuild-index` 端點 logic（未來新增租戶 / 新 collection 用）|
| `apps/backend/src/application/conversation/list_conv_summaries_use_case.py` | 分頁 + tenant/bot filter |
| `apps/backend/src/interfaces/api/admin_chunk_router.py` | |
| `apps/backend/src/interfaces/api/admin_milvus_router.py` | |
| `apps/backend/src/interfaces/api/admin_conv_summary_router.py` | |

### 新建（frontend）

| 檔案 | 職責 |
|------|------|
| `apps/frontend/src/types/chunk.ts` | `Chunk`, `UpdateChunkRequest`, `RetrievalTestRequest/Result`, `ChunkListFilter` |
| `apps/frontend/src/types/milvus.ts` | `CollectionInfo`, `CollectionStats` |
| `apps/frontend/src/hooks/queries/use-kb-chunks.ts` | useKbChunks / useUpdateChunk / useDeleteChunk / useReEmbedChunk |
| `apps/frontend/src/hooks/queries/use-retrieval-test.ts` | useRetrievalTest mutation |
| `apps/frontend/src/hooks/queries/use-milvus.ts` | useMilvusCollections / useCollectionStats / useRebuildIndex |
| `apps/frontend/src/hooks/queries/use-conv-summaries.ts` | useConvSummaries |
| `apps/frontend/src/pages/admin-kb-studio.tsx` | 容器（URL tab state via `useSearchParams`） |
| `apps/frontend/src/pages/admin-milvus.tsx` | Milvus dashboard |
| `apps/frontend/src/pages/admin-conversation-summary.tsx` | |
| `apps/frontend/src/features/admin/kb-studio/kb-studio-tabs.tsx` | Tab container |
| `apps/frontend/src/features/admin/kb-studio/overview-tab.tsx` | 從 `admin-kb-detail.tsx` 遷入 |
| `apps/frontend/src/features/admin/kb-studio/chunks-tab.tsx` | `@tanstack/react-virtual` list + inline edit |
| `apps/frontend/src/features/admin/kb-studio/chunk-editor.tsx` | textarea autosave（debounce 1s）+ re-embed button |
| `apps/frontend/src/features/admin/kb-studio/retrieval-playground-tab.tsx` | Query + top-K slider + 結果卡片 + conv-summary cross-search toggle |
| `apps/frontend/src/features/admin/kb-studio/categories-tab.tsx` | CRUD + HTML5 native drag reassign |
| `apps/frontend/src/features/admin/kb-studio/quality-tab.tsx` | 複用 useDocumentQualityStats + KB-level summary card |
| `apps/frontend/src/features/admin/kb-studio/settings-tab.tsx` | embedding / context / classification model 切換 |
| `apps/frontend/src/features/knowledge/components/chunk-card.tsx` | 共用：`mode: "view" \| "edit" \| "compact"` |
| `apps/frontend/src/components/ui/confirm-danger-dialog.tsx` | O10 標準化（輸入資源名確認）|
| `apps/frontend/src/features/admin/milvus/collection-table.tsx` | |
| `apps/frontend/src/features/admin/milvus/collection-stats-card.tsx` | |
| `apps/frontend/src/features/admin/conv-summary/conv-summary-list.tsx` | |
| `apps/frontend/src/features/admin/conv-summary/conv-summary-search-panel.tsx` | |

---

## API Endpoints（新增 13 個）

### Chunk 操作（`admin_chunk_router`）

| Method | Path | Use case | 權限 |
|---|---|---|---|
| GET | `/api/v1/admin/knowledge-bases/{kb_id}/chunks?page=&category_id=` | ListKbChunks | system_admin + tenant_admin（驗 kb.tenant_id）|
| PATCH | `/api/v1/admin/documents/{doc_id}/chunks/{chunk_id}` | UpdateChunk | 同上 + 驗 chunk→doc→kb→tenant chain |
| POST | `/api/v1/admin/chunks/{chunk_id}/re-embed` | ReEmbedChunk | 同上 |
| DELETE | `/api/v1/admin/chunks/{chunk_id}` | DeleteChunk | 同上 |
| POST | `/api/v1/admin/knowledge-bases/{kb_id}/retrieval-test` | TestRetrieval | 同上 + body 含 `include_conv_summaries: bool` |
| GET | `/api/v1/admin/knowledge-bases/{kb_id}/quality-summary` | GetKbQualitySummary | 同上 |

### Category CRUD（延伸既有 `knowledge_base_router.py` line 213 附近）

| Method | Path | Use case |
|---|---|---|
| POST | `/api/v1/knowledge-bases/{kb_id}/categories` | CreateCategory |
| DELETE | `/api/v1/knowledge-bases/{kb_id}/categories/{cat_id}` | DeleteCategory |
| POST | `/api/v1/knowledge-bases/{kb_id}/categories/{cat_id}/assign-chunks` | AssignChunks |

### Milvus Dashboard

| Method | Path | Use case |
|---|---|---|
| GET | `/api/v1/admin/milvus/collections` | ListCollections |
| GET | `/api/v1/admin/milvus/collections/{name}/stats` | GetCollectionStats |
| POST | `/api/v1/admin/milvus/collections/{name}/rebuild-index` | RebuildIndex（未來新增 collection 用）|

### Conv Summary

| Method | Path | Use case |
|---|---|---|
| GET | `/api/v1/admin/conv-summaries?tenant_id=&bot_id=&page=` | ListConvSummaries |
| POST | `/api/v1/admin/conv-summaries/search` | 複用既有 `search_conv_summaries` |

---

## 實作順序（約 9-10d）

### Stage 0 已完成

- [x] Day 0a: Milvus INVERTED hotfix commit `660008a`
- [x] Day 0b: Rebuild script commit `1c773d9` + 跑過 local + dev-vm
- [x] Plan 同步 commit `54d3016` + 當前全域 plan

### Stage 1 — DDD 設計（本 plan）

### Stage 2 — BDD feature 先寫（~1d）

9 個 `.feature` 檔：

| 檔案 | Scenarios |
|---|---|
| `tests/features/unit/knowledge/update_chunk.feature` | Happy path + tenant chain 驗證 + debounce autosave + re-embed enqueue |
| `tests/features/unit/knowledge/delete_chunk.feature` | DB+Milvus 雙階段 + 失敗處理 |
| `tests/features/unit/knowledge/list_kb_chunks.feature` | 分頁 + category filter + 跨租戶隔離 |
| `tests/features/unit/knowledge/test_retrieval.feature` | Playground top-K + tenant filter 必帶 + filter_expr 曝露 |
| `tests/features/unit/knowledge/reembed_chunk.feature` | arq job happy path + Milvus upsert_single + RecordUsage 寫入 |
| `tests/features/unit/chunk_category/category_crud.feature` | Create / Delete / AssignChunks + tenant boundary |
| `tests/features/unit/milvus/list_collections.feature` | platform_admin 全部 / tenant_admin 過濾 + INVERTED index 顯示 |
| `tests/features/unit/conversation/list_conv_summaries.feature` | tenant/bot filter + 404 防枚舉 |
| `tests/features/integration/admin/admin_kb_studio_api.feature` | E2E：6 chunk + 3 category + 3 milvus + 2 conv-summary endpoint + 跨租戶 404 |

### Stage 3 — TDD step_defs（~1.5d）

對應 9 feature 檔的 `_steps.py`，全部用 AsyncMock + FakeRepo pattern（mirror Pricing sprint）。

### Stage 4 — 實作（~5-6d）

**Day 1**：VectorStore interface 5 方法 + Milvus infra 實作（`asyncio.to_thread` 包）；DocumentRepository 5 方法 + ChunkCategoryRepository 2 方法
**Day 2**：12 個 use cases + `reembed_chunk` arq job + 擴充 `RetrieveResult` 加 filter_expr；全部 use case 第一行強制 tenant chain 驗證
**Day 3**：3 新 router + `knowledge_base_router` 加 3 category endpoint + container.py 註冊 + main.py wire；跑通 integration test + 跨租戶 404
**Day 4**：前端 types + 4 hooks + `admin-kb-studio.tsx` 容器 + Overview / Documents / Settings tab（遷 `admin-kb-detail.tsx` 內容；加 @tanstack/react-virtual 依賴）
**Day 5**：Chunks tab — `<ChunkCard>` 共用元件 + `chunk-editor.tsx` (inline edit + debounce 1s autosave) + virtual scroll list
**Day 6**：Retrieval Playground（含 conv-summary cross-search toggle）+ Categories tab（CRUD + HTML5 native drag reassign）
**Day 7**：Milvus Dashboard 頁 + Conv Summary 頁 + `<ConfirmDangerDialog>` 標準化 + 既有危險操作遷移（kb delete / batch delete / batch reprocess）

### Stage 5 — 驗證交付（~1d）

- `cd apps/backend && uv run python -m pytest tests/ -v`
- `cd apps/frontend && npx vitest run`
- `npx tsc --noEmit` 不新增 error
- Ruff / mypy 綠
- 手動 E2E 10 步（見 Verification）
- Commit 分 5-6 邏輯 commit（非單一 mega）
- 架構筆記 → `docs/architecture-journal.md`（主題「自建 vs 整合開源 UI 取捨 + HTML5 drag 取代 dnd-kit 的成本評估」）
- SPRINT_TODOLIST 同步
- Close Issue

---

## Critical Files（可重用資產）

| 職責 | 檔案 | 怎麼用 |
|---|---|---|
| Milvus scalar index（已 hotfix）| `apps/backend/src/infrastructure/milvus/milvus_vector_store.py:96-102` | 所有新方法照 `asyncio.to_thread()` 包裹 |
| Milvus filter 注入防護 | `apps/backend/src/infrastructure/milvus/milvus_vector_store.py:40` (`_build_filter_expr`) | Playground 不可繞過直接拼 filter |
| ChunkCategory router | `apps/backend/src/interfaces/api/knowledge_base_router.py:213-309` | 新 3 endpoint 延伸於此 |
| ChunkCategoryRepository | `apps/backend/src/infrastructure/db/repositories/chunk_category_repository.py:11-115` | 既有 `update_chunks_category` 可接 assign |
| DocumentRepository chunk 方法 | `apps/backend/src/infrastructure/db/repositories/document_repository.py:276-374` | 已有 8 方法可重用；新增 5 方法 |
| RAG retrieve pipeline | `apps/backend/src/application/rag/query_rag_use_case.py:199` (`retrieve()`) | Playground 薄 wrapper 直接呼叫；加 filter_expr 曝露 |
| Tenant auth | `apps/backend/src/interfaces/api/deps.py:21-64` (`get_current_tenant`) | 所有新 endpoint 必用 |
| Admin router 最新範本 | `apps/backend/src/interfaces/api/admin_pricing_router.py`（S-Pricing.1） | 複製結構 + Pydantic schema 風格 |
| arq worker 模式 | `apps/backend/src/worker.py:27-30` (`_new_container`) + `:50` (process_document_task) | `reembed_chunk` 照抄 |
| Chunk 既有元件 | `apps/frontend/src/features/knowledge/components/category-list.tsx` + `chunk-preview-panel.tsx` | 抽 `<ChunkCard>` 共用 |
| Admin page 最新範本 | `apps/frontend/src/pages/admin-pricing.tsx`（S-Pricing.1） | 複製 |
| Sidebar 插入點 | `apps/frontend/src/components/layout/sidebar.tsx:53` (after `/admin/pricing`) | 加 3 項後 |
| App.tsx 路由插入 | `apps/frontend/src/App.tsx:~194` (after ADMIN_PRICING) | lazy + AdminRoute 內 |
| AlertDialog 範本 | `apps/frontend/src/features/knowledge/components/document-list.tsx:229-260` | `<ConfirmDangerDialog>` 抽取源 |

---

## 多租戶安全紅線（8 條）

1. **每個 chunk/category use case 第一行**：`kb = kb_repo.find_by_id(kb_id)` → `assert kb.tenant_id == tenant.tenant_id`（Phase 1 探索顯示這個 chain 目前 **未被貫徹執行**，plan 必須補）
2. Platform admin vs tenant admin：`Depends(require_role("system_admin"))` / `Depends(require_role("tenant_admin"))` 分流
3. URL `kb_id` / `chunk_id` 不屬 caller tenant → **回 404** 不 403（防枚舉）
4. Retrieval Playground Milvus search 一律帶 `tenant_id` filter；platform admin 跨租戶觀察要顯示「身份 X」banner + 帶 X 的 filter
5. Milvus collection list：tenant admin 只看自己 KB 的 `kb_*`；platform admin 才看 `conv_summaries`
6. Chunk re-embed 必須同步寫 Milvus payload `tenant_id`（不能只改 DB；`upsert_single` 要強制要求 payload 有 tenant_id）
7. Playground 不開放使用者自由輸入 filter expression — 只用 dropdown 選 KB / category
8. Conv Summary 跨 bot filter `bot_id` 必須驗屬 caller tenant；禁 platform admin 無 tenant filter 撈全集

---

## Audit Hook 預埋（延續 S-Pricing.1 pattern）

所有 write use case 收尾打 structlog（欄位對齊未來 `audit_log` 表）：

- `kb_studio.chunk.update` — {chunk_id, kb_id, tenant_id, actor, content_diff_len}
- `kb_studio.chunk.delete` — {chunk_id, kb_id, tenant_id, actor}
- `kb_studio.chunk.reembed` — {chunk_id, kb_id, model, token_cost, actor}
- `kb_studio.category.create` / `.delete` / `.assign` — {cat_id, kb_id, chunk_count, actor}
- `kb_studio.milvus.rebuild_index` — {collection, field, index_type, actor}

上線前 `memory/audit-trail-pre-production.md` 建 `audit_log` 表時對齊 event 名。

---

## 風險與備案

| 風險 | 應對 |
|---|---|
| 單 chunk re-embed 併發寫 Milvus 衝突 | arq queue 天然序列化 per worker；同 chunk_id upsert 冪等（Milvus 覆蓋語意）|
| Inline edit autosave 網路抖動失敗 | UI toast + 3 次 retry + 放棄後顯示「本地有未儲存變更」 |
| Virtual scroll > 10K chunks 效能 | `@tanstack/react-virtual` cursor pagination + estimateSize 調校 |
| Conv Summary cross-search 慢 | Milvus 兩 collection 並發查 + 各自 top-K=10 → 前端合併排序（標示來源）|
| Categories HTML5 drag 跨 tenant 風險 | drop handler 必須 re-驗 chunk.tenant_id（不信任 drag data）|
| Categories drag 大量 chunk 不流暢 | drag 是 optimistic UI，背景 bulk PATCH；失敗全 rollback |
| KB Studio 路由與 admin-kb-detail 衝突 | Day 4 把舊 route 改 redirect，保留 3 sprint 後刪 |
| `tenant_id` 寫入 Milvus payload 時缺值 | `upsert_single` 必填參數 + domain entity schema 驗證 |

---

## 不在本 Sprint 範圍

- O3 DocumentQualityStats 前端完整串接（本 sprint 僅做 summary card）
- O4 Chunk referenced-by-conversations endpoint（P3）
- O5 三個 KB 詳細頁資料層統一（下 sprint）
- O6 命名一致化 + router 拆分（下 sprint）
- O11 Toast 標準化攔截器（P2）
- 實體 `audit_log` 資料表建置（structlog event 先預埋）
- Multi-pod `PricingCache` Redis pub/sub（S-Pricing.1 遺留）
- 單 chunk delete Milvus 失敗 retry queue（P1，看實測頻率再決定）

---

## 六階段合規

- [x] Stage 0 — Plan 已落地（本檔）；Issue Stage 2 前建
- [x] Stage 1 — DDD 設計：新 `application/chunk_category/` + `application/milvus/` + `application/conversation/list_conv_summaries` 跨 context，4 層落點明確
- [ ] Stage 2 — BDD：9 個 `.feature`
- [ ] Stage 3 — TDD：9 個 `_steps.py` 紅燈
- [ ] Stage 4 — 實作：Day 1-7
- [ ] Stage 5 — 交付：全量測試 + lint + 10 步手動 E2E + close Issue + 架構筆記

---

## Verification

### 單元測試

```bash
cd apps/backend
uv run python -m pytest tests/unit/knowledge/ tests/unit/chunk_category/ tests/unit/milvus/ tests/unit/conversation/ -v --tb=short
uv run ruff check src/ && uv run mypy src/
```

### 整合測試

```bash
uv run python -m pytest tests/integration/admin/test_admin_kb_studio_api_steps.py -v
```

### 前端測試

```bash
cd apps/frontend
npx vitest run
npx tsc --noEmit
```

### 手動 E2E（10 步，local-docker）

1. system_admin 登入 → `/admin/knowledge-bases` 看 KB 列表
2. 點 KB row → `/admin/kb-studio/{kbId}?tab=overview` 顯示 KB 基本資訊（從舊 admin-kb-detail 遷入的）
3. 切 Chunks tab → 看 virtualized list（滾 1000+ chunks 流暢）
4. 雙擊一個 chunk content → inline 改文字 → 等 1.5 秒 toast「儲存 + re-embedding...」
5. 等 arq 完成 → Milvus 直接查該 chunk_id，向量已變
6. 切 Playground tab → 輸入 query → 回 top-5 + score + filter expression 顯示
7. 打開 conv-summary cross-search toggle → 結果多一區「對話摘要」
8. 切 Categories tab → 新增分類「測試」→ HTML5 drag 一個 chunk 過去 → 確認 DB + Milvus payload 更新
9. `/admin/milvus` → 看到所有 `kb_*` collection row count / tenant_id index 為 `INVERTED`
10. 切 tenant_admin 身份訪問別租戶 `kb_id` URL → 回 **404**（不是 403）
