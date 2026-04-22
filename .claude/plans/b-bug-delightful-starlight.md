# Plan: S-KB-Studio.1 — 自建 KB Studio（RAGFlow UX，shadcn 實作）

> 取代 S-Pricing.1（已 ship commit `3e2173a` + `acdf0f0`）。本 plan 落地 2026-04-22 凌晨兩個 Plan agent 的 KB Studio 提案，原始提案來自 session `c23d5bd2-c2aa-4c30-8c52-2064c2d0932c` 對話 index 3239/3244。
>
> **GitHub Issue**：待建（Stage 0 先開）
> **合併範圍**：原 Phase 1 (6d) + Phase 2 (6d) 合成單一 sprint，扣掉已完成的 O13 (prompt cache) 實際 ~10-11d

---

## Context

### 為何現在做

1. RAG 品質除錯沒有工具 — 目前 admin 只能 upload / delete 整份文件。chunk 分類不對、context_text 不準、retrieval 結果差時無法 inline 修正，只能重新上傳整文（成本 = 文件 chunk 數 × embedding 費）
2. ChunkCategory Auto-Classification 已在跑，但分類結果是「黑盒」— 沒 UI 可改名、合併、強制重指派
3. 無 Retrieval Playground — 上線前沒工具驗「使用者問 X 會檢索到 Y」
4. Milvus 基礎設施沒可視化 — collection 數量、row count、index 狀態全要 SSH 進 VM 才看得到
5. **Milvus `tenant_id` scalar index 當前為空字串 → 實測走 full scan**（`milvus_vector_store.py:94-95`），隨租戶資料量成長會雪崩

### 路線決策（已與 Larry 對齊 2026-04-22）

**不用 RAGFlow（路線 A/C），自建（路線 B）**。三條致命原因：
- 資料模型不相容（RAGFlow 自有 Postgres schema vs 我們 MySQL + DDD 4-layer + 17 use cases）
- 租戶模型不相容（RAGFlow tenant = 個人空間，沒 `tenant_id` row-level filter → 破壞多租戶隔離）
- Conv Summary / Auto-Classification / Contextual Retrieval 既有邏輯要廢重接

**參考 RAGFlow UX 哲學**（左欄樹狀導覽 / 右欄 detail tabs / chunk inline edit / retrieval test panel），元件全用 shadcn 自刻。

### 現況（S-LLM-Cache.1 + S-Pricing.1 ship 後）

| 原提案 P0 優化 | 狀態 |
|---|---|
| O13 Contextual Retrieval prompt caching | ✅ S-LLM-Cache.1 已 ship |
| O14 Milvus tenant_id scalar index | ⚠️ 仍 `index_type=""` 走 full scan |
| O1 ChunkCategory CRUD 補齊 | ⚠️ 仍缺 POST/DELETE/assign |
| O2+O12 單 chunk edit + arq re-embed | ⚠️ 未做 |
| O10 ConfirmDangerDialog 標準化 | ⚠️ 未做 |
| O15/O16 tenant boundary | ⚠️ 未做 |

### 成功條件（全部必達才算完 sprint）

- Admin 進 `/admin/kb-studio/{kbId}` 看到 7 tabs 全正常（overview / documents / chunks / categories / playground / quality / settings）
- Chunks tab inline 編輯 chunk 內容 → 自動 debounce 1s 觸發 re-embed → Milvus upsert 新向量
- Retrieval Playground 輸入 query，回 top-K 帶 score + 可看到 filter expression
- Categories tab 可 CRUD 分類 + drag 把 chunk 搬到別分類
- Milvus Dashboard 列出所有 collection + row count + index type（`tenant_id` 顯示 `STL_SORT` 非空字串）
- `tenant_admin` 訪問別租戶 `:kbId` → 回 404（不 403 防枚舉）
- 單 chunk re-embed 省 > 80% embedding token（vs 整文 reprocess）
- 全量測試綠 + 覆蓋率不降

---

## Design Decisions（已與 Larry 對齊）

1. **自建 KB Studio，不引入 RAGFlow**（見上方「路線決策」）
2. **廢掉 `admin-kb-detail.tsx` 唯讀頁**，內容遷入 KB Studio Overview tab，舊 route redirect
3. **Phase 1 + Phase 2 合併為單一 sprint**（Larry 確認 2026-04-22，總工時 ~10-11d）
4. **Conv Summary 獨立 sidebar，不塞 KB Studio**；KB Studio Playground 加 toggle「也搜尋對話摘要」做 cross-search
5. **O14 Milvus index 修正當 Day 0 hotfix 先 ship**（1 小時工作量，避免 sprint 期間雪崩）
6. **單 chunk re-embed 走 arq job**（`reembed_chunk`），不走 7 步 pipeline
7. **Inline edit 用 textarea + debounce 1s autosave**（不用 contenteditable 避免格式污染）
8. **Chunk list 用 virtuoso virtual scroll**（KB 可能上萬 chunks，傳統 pagination UX 差）
9. **租戶邊界驗證紅線**：所有 chunk/category endpoint 必須從 JWT 取 tenant_id，URL path 帶 `kb_id` 先驗歸屬，404 防枚舉

---

## Day 0 Hotfix — O14 Milvus Index（先 ship）

### 檔案

- `apps/backend/src/infrastructure/milvus/milvus_vector_store.py:94-95`

### 變更

```python
# Before
index_params.add_index(field_name="tenant_id", index_type="")

# After
index_params.add_index(field_name="tenant_id", index_type="INVERTED")
```

（`STL_SORT` 適用數值欄位，`tenant_id` 是字串 → `INVERTED`。Milvus 2.4+ 原生支援。）

### 驗證

```python
# 確認 document_id 也有 scalar index
grep -A 2 'field_name="document_id"' apps/backend/src/infrastructure/milvus/milvus_vector_store.py
# 若沒有 → 一併加 INVERTED
```

### 現有 collection 影響

- 新 collection 自動用新 index
- 舊 collection 需 `drop_index() → create_index() → load()` 重建
- **✅ 2026-04-22 已完成**：`scripts/rebuild_milvus_scalar_index.py` 跑過 local-docker (2 coll) + dev-vm (6 coll + conv_summaries)，全部雙欄位升成 INVERTED。Day 7 `/admin/milvus/collections/{name}/rebuild-index` endpoint 仍會實作（供未來個案或新增租戶後使用），但現有 collection **不用再 rebuild**

### BDD + TDD

- `tests/features/unit/milvus/tenant_index.feature`：驗 collection 建立時 tenant_id index 非空
- `tests/unit/milvus/test_tenant_index.py`：mock pymilvus client，驗 `add_index` call 帶 `index_type="INVERTED"`

Ship 為獨立 commit，title：`fix(rag): S-KB-Studio.0 Milvus tenant_id scalar index 從空字串改 INVERTED`

---

## 資料模型 / 新增 migration

### 不需要新 table（只擴 domain interface + infra）

本 sprint 主要是 **讀寫既有 `chunks` + `chunk_categories` + Milvus + 新 endpoint**，不新建 DB 表。

### 可能需要的 ORM 修改

- `ChunkModel` 視 inline edit 流程加 `updated_at` trigger（若無）
- `ChunkCategoryModel` 確認 `deleted_at` soft delete 欄位（或硬刪含 chunks 設 category_id=NULL 的 cascade）

---

## DDD 檔案落點

### 修改 / 擴充（backend）

| 檔案 | 變更 |
|------|------|
| `apps/backend/src/infrastructure/milvus/milvus_vector_store.py` | Day 0 hotfix + 新方法 `list_collections`, `get_collection_stats`, `update_payload`, `count_by_filter`, `upsert_single(collection, id, vector, payload)` |
| `apps/backend/src/domain/rag/services.py` (VectorStore interface) | 加 5 個新抽象方法（對應 infra 實作） |
| `apps/backend/src/domain/knowledge/repository.py` | 加 `update_chunk`, `find_chunk_by_id`, `find_chunks_by_kb_paginated`, `count_chunks_by_kb`, `delete_chunk` |
| `apps/backend/src/domain/knowledge/entity.py` | `Chunk` entity 可能加 `updated_at` + `category_id` mutability |
| `apps/backend/src/domain/knowledge/chunk_category.py` | `ChunkCategoryRepository` 加 `delete_by_id`, `assign_chunks` |
| `apps/backend/src/infrastructure/db/repositories/document_repository.py` | 實作上述 chunk 擴充方法 |
| `apps/backend/src/infrastructure/db/repositories/chunk_category_repository.py` | 實作 delete_by_id + assign_chunks |
| `apps/backend/src/container.py` | 註冊 8+ 新 use cases + wiring 加 3 個新 router |
| `apps/backend/src/main.py` | include 新 router（admin_chunk / admin_milvus / admin_conv_summary） |
| `apps/backend/src/worker.py` | 加 `reembed_chunk` arq job |
| `apps/frontend/src/App.tsx` | 加 3 新 routes：`ADMIN_KB_STUDIO`, `ADMIN_MILVUS`, `ADMIN_CONV_SUMMARY` |
| `apps/frontend/src/routes/paths.ts` | 同上 3 const + 棄用 `ADMIN_KB_DETAIL` 加 redirect |
| `apps/frontend/src/components/layout/sidebar.tsx` | 加 3 新入口（icon 建議：`Library` / `Database` / `MessagesSquare`） |
| `apps/frontend/src/lib/api-endpoints.ts` | 加 `adminChunks`, `adminMilvus`, `adminConvSummary` namespace |
| `apps/frontend/src/hooks/queries/keys.ts` | 加對應 query keys |

### 新建（backend）

| 檔案 | 職責 |
|------|------|
| `apps/backend/src/application/knowledge/update_chunk_use_case.py` | 驗 tenant → DB update → enqueue reembed_chunk |
| `apps/backend/src/application/knowledge/reembed_chunk_use_case.py` | 單 chunk embedding → Milvus upsert（arq job 實際 handler） |
| `apps/backend/src/application/knowledge/delete_chunk_use_case.py` | DB delete + Milvus delete（兩階段 + 失敗 log） |
| `apps/backend/src/application/knowledge/list_kb_chunks_use_case.py` | 分頁 + category filter |
| `apps/backend/src/application/knowledge/test_retrieval_use_case.py` | embed query → Milvus search 帶 tenant filter + debug info |
| `apps/backend/src/application/knowledge/get_kb_quality_summary_use_case.py` | KB-level quality 聚合（低分 chunk 數、平均聚合度） |
| `apps/backend/src/application/chunk_category/create_category_use_case.py` | 新增分類（手動） |
| `apps/backend/src/application/chunk_category/delete_category_use_case.py` | 刪除分類 + 級聯 chunks 設 NULL |
| `apps/backend/src/application/chunk_category/assign_chunks_use_case.py` | 批次把 chunks 指給某 category |
| `apps/backend/src/application/milvus/list_collections_use_case.py` | 列 collection + tenant filter（platform admin 全部、tenant admin 過濾） |
| `apps/backend/src/application/milvus/get_collection_stats_use_case.py` | row count / index / memory |
| `apps/backend/src/application/conversation/list_conv_summaries_use_case.py` | 分頁 + tenant/bot filter |
| `apps/backend/src/interfaces/api/admin_chunk_router.py` | URL prefix `/api/v1/admin`，endpoints 見下方 |
| `apps/backend/src/interfaces/api/admin_milvus_router.py` | `/api/v1/admin/milvus/*` |
| `apps/backend/src/interfaces/api/admin_conv_summary_router.py` | `/api/v1/admin/conv-summaries/*` |

### 新建（frontend）

| 檔案 | 職責 |
|------|------|
| `apps/frontend/src/types/chunk.ts` | `Chunk`, `UpdateChunkRequest`, `RetrievalTestRequest/Result`, `ChunkListFilter` |
| `apps/frontend/src/types/milvus.ts` | `CollectionInfo`, `CollectionStats` |
| `apps/frontend/src/hooks/queries/use-kb-chunks.ts` | useKbChunks / useUpdateChunk / useDeleteChunk / useReEmbedChunk |
| `apps/frontend/src/hooks/queries/use-retrieval-test.ts` | useRetrievalTest mutation |
| `apps/frontend/src/hooks/queries/use-milvus.ts` | useMilvusCollections / useCollectionStats |
| `apps/frontend/src/hooks/queries/use-conv-summaries.ts` | useConvSummaries |
| `apps/frontend/src/pages/admin-kb-studio.tsx` | 容器（useSearchParams tab state） |
| `apps/frontend/src/pages/admin-milvus.tsx` | Milvus dashboard |
| `apps/frontend/src/pages/admin-conversation-summary.tsx` | Conv Summary 管理頁 |
| `apps/frontend/src/features/admin/kb-studio/kb-studio-tabs.tsx` | Tab navigation container |
| `apps/frontend/src/features/admin/kb-studio/overview-tab.tsx` | 從 admin-kb-detail 遷入 |
| `apps/frontend/src/features/admin/kb-studio/chunks-tab.tsx` | virtuoso virtual scroll + inline edit |
| `apps/frontend/src/features/admin/kb-studio/chunk-editor.tsx` | textarea autosave（debounce 1s）+ re-embed button |
| `apps/frontend/src/features/admin/kb-studio/retrieval-playground-tab.tsx` | Query input + top-K slider + 結果卡片 + conv-summary cross-search toggle |
| `apps/frontend/src/features/admin/kb-studio/categories-tab.tsx` | CRUD + drag-to-reassign（react-dnd 或 dnd-kit） |
| `apps/frontend/src/features/admin/kb-studio/quality-tab.tsx` | 複用 useDocumentQualityStats + KB-level summary card |
| `apps/frontend/src/features/admin/kb-studio/settings-tab.tsx` | embedding / context / classification model 切換 |
| `apps/frontend/src/features/knowledge/components/chunk-card.tsx` | 共用 component，`mode: "view" | "edit" | "compact"` |
| `apps/frontend/src/components/ui/confirm-danger-dialog.tsx` | O10 標準化 — 要求輸入資源名稱才能 enable 刪除按鈕 |
| `apps/frontend/src/features/admin/milvus/collection-table.tsx` | |
| `apps/frontend/src/features/admin/milvus/collection-stats-card.tsx` | |
| `apps/frontend/src/features/admin/conv-summary/conv-summary-list.tsx` | |
| `apps/frontend/src/features/admin/conv-summary/conv-summary-search-panel.tsx` | |

---

## API Endpoints（新增 13 個）

### Chunk 操作（`admin_chunk_router`）

| Method | Path | Use case | 權限 |
|---|---|---|---|
| GET | `/api/v1/admin/knowledge-bases/{kb_id}/chunks?page=&category_id=` | ListKbChunks | system_admin + tenant_admin (驗 kb.tenant_id) |
| PATCH | `/api/v1/admin/documents/{doc_id}/chunks/{chunk_id}` | UpdateChunk | 同上 + 驗 chunk→doc→kb→tenant |
| POST | `/api/v1/admin/chunks/{chunk_id}/re-embed` | ReEmbedChunk | 同上 |
| DELETE | `/api/v1/admin/chunks/{chunk_id}` | DeleteChunk | 同上 |
| POST | `/api/v1/admin/knowledge-bases/{kb_id}/retrieval-test` | TestRetrieval | 同上 + body 含 `include_conv_summaries: bool` |
| GET | `/api/v1/admin/knowledge-bases/{kb_id}/quality-summary` | GetKbQualitySummary | 同上 |

### Category CRUD（延伸既有 router）

| Method | Path | Use case |
|---|---|---|
| POST | `/api/v1/admin/knowledge-bases/{kb_id}/categories` | CreateCategory |
| DELETE | `/api/v1/admin/knowledge-bases/{kb_id}/categories/{cat_id}` | DeleteCategory |
| POST | `/api/v1/admin/knowledge-bases/{kb_id}/categories/{cat_id}/assign-chunks` | AssignChunks（body: chunk_ids[]） |

### Milvus Dashboard

| Method | Path | Use case |
|---|---|---|
| GET | `/api/v1/admin/milvus/collections` | ListCollections（tenant_admin 過濾） |
| GET | `/api/v1/admin/milvus/collections/{name}/stats` | GetCollectionStats |
| POST | `/api/v1/admin/milvus/collections/{name}/rebuild-index` | 重建 scalar index（給 Day 0 舊 collection 更新用） |

### Conv Summary

| Method | Path | Use case |
|---|---|---|
| GET | `/api/v1/admin/conv-summaries?tenant_id=&bot_id=&page=` | ListConvSummaries |
| POST | `/api/v1/admin/conv-summaries/search` | 複用既有 `search_conv_summaries` |

---

## 實作順序（六階段，約 10-11d）

### Stage 0 — Issue + 本 plan 已建
- ✅ 本 plan file（2026-04-22）
- [ ] `gh issue create` 開 S-KB-Studio.1 Issue（Day 0 hotfix 前建）

### Stage 1 — DDD 設計：已完成於本 plan

### Stage 2 — BDD feature 先寫（~1d）

| Feature 檔 | Scenarios |
|---|---|
| `tests/features/unit/milvus/tenant_index.feature` | Day 0 hotfix：collection 建立含 INVERTED index |
| `tests/features/unit/knowledge/update_chunk.feature` | Happy path + tenant boundary + debounce autosave + re-embed enqueue |
| `tests/features/unit/knowledge/delete_chunk.feature` | DB + Milvus 雙階段 + 失敗 retry |
| `tests/features/unit/knowledge/list_kb_chunks.feature` | 分頁 + category filter + 跨租戶隔離 |
| `tests/features/unit/knowledge/test_retrieval.feature` | Playground top-K + tenant filter 必帶 + filter expression 顯示 |
| `tests/features/unit/knowledge/reembed_chunk.feature` | arq job happy path + Milvus upsert 覆蓋 + token 記錄 |
| `tests/features/unit/chunk_category/category_crud.feature` | Create / Delete / AssignChunks |
| `tests/features/unit/milvus/list_collections.feature` | platform_admin 看全部 / tenant_admin 過濾 |
| `tests/features/integration/admin/admin_kb_studio_api.feature` | E2E：6 個 chunk endpoint + 3 個 category + 2 個 milvus + 跨租戶 404 |

### Stage 3 — TDD step_defs（~1-1.5d）
對應 9 個 feature 檔的 `_steps.py`，全部用 AsyncMock + FakeRepo 模式（mirror pricing sprint pattern）。

### Stage 4 — 實作（~6-7d）

**Day 0**（當天 ship）：O14 Milvus index hotfix commit
**Day 1**：VectorStore interface + Milvus infra 5 新方法 + DocumentRepository chunk 擴充 + ChunkCategoryRepository 2 方法
**Day 2**：8 個 backend use cases + arq `reembed_chunk` job
**Day 3**：3 個新 router + container.py 註冊 + main.py wire + tenant boundary test 全綠
**Day 4**：前端 types + hooks + `admin-kb-studio.tsx` 容器 + overview / documents / settings tabs（遷移既有）
**Day 5**：Chunks tab — chunk-card + chunk-editor（inline edit + debounce）+ virtuoso virtual scroll
**Day 6**：Retrieval Playground tab（含 conv-summary cross-search toggle）+ Categories tab（CRUD + drag-to-reassign）
**Day 7**：Milvus Dashboard 頁 + Conv Summary 頁
**Day 8**：`<ConfirmDangerDialog>` 標準化 + 既有危險操作遷移（kb delete、batch delete、batch reprocess）

### Stage 5 — 驗證交付（~1-1.5d）

- `uv run python -m pytest tests/ -v`（unit + integration 全綠）
- `npx vitest run`
- `npx tsc --noEmit`（不新增 error）
- 手動 E2E：10 步走一遍（列 chunks → inline edit → 看 Milvus 驗證 vector 更新 → retrieval test → category reassign → milvus dashboard → 跨租戶 404）
- `make lint`
- Commit 系列（建議 5-6 個邏輯 commit 非單一 mega-commit）
- 架構筆記 → `docs/architecture-journal.md`（主題「自建 vs 整合開源 UI 的取捨」）
- SPRINT_TODOLIST 同步
- Close Issue

---

## Critical Files（可重用資產）

| 職責 | 檔案 | 怎麼用 |
|---|---|---|
| Milvus scalar index 現況 | `apps/backend/src/infrastructure/milvus/milvus_vector_store.py:94-95` | Day 0 hotfix 目標 |
| Milvus filter 注入防護 | `apps/backend/src/infrastructure/milvus/milvus_vector_store.py:29` (`_sanitize_filter_value`) | Retrieval Playground 不可繞過 |
| ChunkCategory 既有 CRUD | `apps/backend/src/application/chunk_category/` | 沿用 list / patch / get_chunks，擴充 create/delete/assign |
| Contextual Retrieval | `apps/backend/src/infrastructure/context/llm_chunk_context_service.py` | S-LLM-Cache.1 已加 prompt cache，不動；只是 chunk 內容改了會重新觸發（走 arq） |
| DocumentQualityStats | 既有 `get_document_quality_stats` + 前端 `useDocumentQualityStats` | Quality tab 聚合用 |
| Conv Summary 搜尋 | `apps/backend/src/application/conversation/search_conversations_use_case.py` | Playground cross-search toggle 呼叫 |
| Tenant boundary helper | `apps/backend/src/interfaces/api/deps.py:67` (`require_role`) | 所有新 router 必用 |
| Admin router 範本 | `apps/backend/src/interfaces/api/admin_pricing_router.py`（S-Pricing.1） | 最新 pattern 參考 |
| Frontend admin 頁範本 | `apps/frontend/src/pages/admin-pricing.tsx`（S-Pricing.1） | 最新 pattern 參考 |
| AlertDialog 範本 | `apps/frontend/src/features/knowledge/components/document-list.tsx:229-260` | O10 ConfirmDangerDialog 抽取來源 |
| 既有 Chunk 唯讀視圖 | `apps/frontend/src/features/knowledge/components/category-list.tsx` | 融入 KB Studio Chunks / Categories tab |

---

## 多租戶安全紅線（8 條）

1. **所有 chunk 操作 use case 第一步：驗 `chunk → document → kb → tenant_id == ctx.tenant_id`**。JWT 取 tenant_id，不信任前端 body。
2. **Platform admin vs Tenant admin** 路由層分流：`Depends(require_platform_admin)` / `Depends(require_tenant_admin)`
3. **URL 帶 `:kbId` 不屬於 caller tenant → 回 404 防枚舉**（不是 403）
4. **Retrieval Playground Milvus search 一律帶 `tenant_id` filter**，platform admin 跨租戶觀察也要有「身份 X」banner + 帶 X 的 filter
5. **Milvus collection list** tenant admin 只看自己 KB 的 `kb_*` collection；platform admin 才看 `conv_summaries` 全部
6. **Chunk re-embed 必須同步寫 Milvus payload `tenant_id`**（不能只改 DB）
7. **Filter 表達式禁用使用者自由輸入**：Playground 只用 dropdown 選 KB / category，不開放文字輸入 filter expr
8. **Conv Summary 跨 bot filter `bot_id` 必須驗證屬於 caller tenant**；禁 platform admin 不帶 tenant filter 搜全部對話摘要

---

## Audit Hook 預埋

延續 S-Pricing.1 模式，所有 write use case 收尾打 structlog：

- `kb_studio.chunk.update` — {chunk_id, kb_id, tenant_id, actor, content_diff_len}
- `kb_studio.chunk.delete` — {chunk_id, kb_id, tenant_id, actor}
- `kb_studio.chunk.reembed` — {chunk_id, kb_id, model, token_cost, actor}
- `kb_studio.category.create` / `.delete` / `.assign` — {cat_id, kb_id, chunk_count, actor}
- `kb_studio.milvus.rebuild_index` — {collection, field, index_type, actor}

上線前 `memory/audit-trail-pre-production.md` 建 audit_log 表時對齊。

---

## 風險與備案

| 風險 | 應對 |
|------|------|
| Milvus rebuild index 期間 collection 不可用 | 加 warning banner + 建議 off-peak；保留 `rebuild-index` endpoint 手動觸發（不自動） |
| 單 chunk re-embed 併發寫 Milvus 衝突 | arq queue 天然序列化；同 chunk_id upsert 冪等（Milvus 覆蓋語意） |
| inline edit autosave 網路抖動失敗 | UI toast + 3 次 retry + 放棄後顯示「本地有未儲存變更」警告 |
| virtuoso virtual scroll 效能 >10K chunks | 分頁 cursor + virtuoso itemHeight estimate + 確認 scroll position 記憶 |
| Conv Summary cross-search 慢 | Milvus 兩個 collection 並發查詢 + 各自 top-K=10 → 前端合併排序（分標示來源） |
| Categories drag-to-reassign 資料量大不流暢 | drag 是 optimistic UI，背景 bulk PATCH，單筆 N/A → 全部 rollback |
| 既有租戶的 Milvus collection 還是空 index | `rebuild-index` API 可批次處理；文件註明手動 trigger |
| KB Studio 路由與 admin-kb-detail 衝突 | Day 4 前端遷移同時把舊 route 改 redirect 到 new route，保留 3 個 sprint 後刪 |

---

## 不在本 Sprint 範圍

- O3 DocumentQualityStats 前端串接（P1 → 先做 summary，完整整合 v2）
- O4 Chunk 被哪些對話引用 endpoint（P3）
- O5 統一三個 KB 詳細頁的資料層（P1 但工程量大 → 下個 sprint）
- O6 命名一致化（純改名，後端 router 拆分留下個 sprint）
- O11 Toast 標準化攔截器（P2）
- 實體 audit_log 資料表建置（structlog event 先預埋，等 POC → 正式上線再補）
- Multi-pod `PricingCache` Redis pub/sub（S-Pricing.1 遺留，正式收費前補）

---

## 六階段合規

- [x] Stage 0 — Plan file 已落地（本檔）；Issue 開起動 sprint 時建
- [x] Stage 1 — DDD 設計：新 `application/chunk_category/` + `application/milvus/` + `application/conversation/` 跨 context，全部 4 層落點明確
- [ ] Stage 2 — BDD：9 個 `.feature` 先寫
- [ ] Stage 3 — TDD：9 個 `_steps.py` 紅燈
- [ ] Stage 4 — 實作：Day 0 hotfix → Day 1-8 主線
- [ ] Stage 5 — 交付：全量測試 + lint + 手動 E2E + close Issue + 架構筆記

---

## Verification

### 單元測試
```bash
cd apps/backend
uv run python -m pytest tests/unit/knowledge/ tests/unit/chunk_category/ tests/unit/milvus/ tests/unit/conversation/ -v --tb=short
uv run ruff check src/
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
1. 以 system_admin 登入 → `/admin/knowledge-bases` 看到 KB 列表
2. 點 KB row → 導向 `/admin/kb-studio/{kbId}?tab=overview`
3. 切 Chunks tab → 看到 virtualized list，滾動流暢
4. 雙擊一個 chunk content → inline 改文字 → 等 1.5 秒看 toast「儲存 + re-embedding...」
5. 等完成（watch arq log）→ Milvus 直接查該 chunk_id 向量變了
6. 切 Playground tab → 輸入 query → 回 top-5 + score + filter expression
7. 打開 conv-summary cross-search toggle → 結果多一區「對話摘要」
8. 切 Categories tab → 新增一個分類「測試」→ drag 一個 chunk 過去
9. `/admin/milvus` → 看到 `kb_xxx` collection row count / tenant_id index 為 `INVERTED`
10. 切 tenant_admin 身份訪問別租戶的 kb_id URL → 回 404
