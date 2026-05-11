-- P0+: Sliced OCR pipeline — per-KB ocr_slice_grid 設定
-- 空字串 = 不切片（既有行為），"RxC" 字串如 "2x3" / "3x2" 啟用 R 列 C 行切片。
-- Splitter wrapper 在 process_document / reprocess image/png 分支讀此欄位。

ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS ocr_slice_grid VARCHAR(16) NOT NULL DEFAULT '';
