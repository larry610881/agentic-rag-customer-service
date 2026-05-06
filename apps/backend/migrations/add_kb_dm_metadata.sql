-- KB-level DM metadata 儲存（Issue #47 / PR-2 L3.1）
-- 動機：5/6 carrefour DM audit 99% chunks 缺活動期間/商家/會員條件等
-- 跨頁共通 metadata。L3 加 KB JSONB 欄位儲存「整本 DM 共通」資訊
-- （DM 期間 / 商家 / 主打商品 / 跨頁活動 / 會員條件）。
-- 由 ExtractKBDMMetadataUseCase 自動萃取（KB 全 docs done 後 trigger）。
-- L4 RAG query path 會把 dm_metadata prepend 到 LLM system context（不重 embed）。

ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS dm_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS dm_metadata_model VARCHAR(100) NOT NULL DEFAULT '';
