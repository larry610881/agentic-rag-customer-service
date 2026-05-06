# DM Page-Type Auto-Dispatch — Baseline & After 比對

## 背景

5/6 carrefour DM (kb_id=`559538a4-d2ac-46e8-8e2c-1d04b599d7e6`) 全 64 頁
reprocess 後發現：原本唯一的 `_CATALOG_PROMPT` 對「信用卡聯名卡 / 會員
活動 / APP 推廣 / 結尾頁」等純優惠頁失效，會 hallucinate 不存在的商品
（如 page 2 抽出「Francasino 自動夾除塵拖」但圖片實際是中國信託 UniOpen
聯名卡介紹）。

本 sprint 在 `claude_vision_ocr.py` 加 page-type detector + 4 個 prompt
（commit `5175e35`）。10 個非純商品頁（4 mixed + 6 promotion）需 reprocess
驗證新 prompt 抽取品質。

## 文件清單

- `baseline.md` — 改 prompt **前**（既有 `_CATALOG_PROMPT`）的 OCR 結果
- `after.md` — 改 prompt **後**（auto-dispatch 走對應 prompt）的 OCR 結果
- 此 README — 操作流程

## 操作流程

### Step 1：把 KB 切到 auto 模式（dev-vm）

```bash
/home/p10359945/google-cloud-sdk/bin/gcloud compute ssh db-services \
  --zone=asia-east1-b --tunnel-through-iap \
  --project=project-4dc6cadb-5d47-4482-a32 \
  --command='docker exec agentic-rag-db psql -U postgres -d agentic_rag -c "
UPDATE knowledge_bases
SET ocr_mode = '\''auto'\''
WHERE id = '\''559538a4-d2ac-46e8-8e2c-1d04b599d7e6'\'';
"'
```

### Step 2：等部署完成

確認 commit `5175e35` 已透過 GitHub Actions auto-deploy 到 Cloud Run。

```bash
/home/p10359945/google-cloud-sdk/bin/gcloud run services describe \
  agentic-rag-backend --region=asia-east1 \
  --format='value(status.latestReadyRevisionName)'
```

### Step 3：透過 KB Studio UI reprocess 10 個 child docs

到 KB Studio 找「家樂福DM」，逐頁 reprocess（或 KB 層 reprocess all）：

| Page | 類型 | child doc id（前 8 字元）|
|---|---|---|
| 2 | promotion | `ec180ec0` 第 2 頁 — 中國信託 UniOpen 聯名卡 |
| 3 | promotion | `032e1707` 第 3 頁 — 生日點數加倍與 APP 會員 |
| 4 | mixed | `c57f18f8` 第 4 頁 — 安心價商品與會員買一送一 |
| 6 | mixed | （見 baseline.md）|
| 8 | promotion | （見 baseline.md）|
| 9 | mixed | （見 baseline.md）|
| 10 | promotion | `097f617b` 第 10 頁 — 家樂福減塑環保四大行動 |
| 11 | promotion | `fbbb3fc1` 第 11 頁 — 博物館特展與友善生態商品 |
| 47 | mixed | `49ed816b` 第 47 頁 — 冷凍冰品飲料與冷藏食品 |
| 64 | promotion | `35b8f1b5` 第 64 頁 — 家樂福禮券與每日優惠 |

### Step 4：撈 after.md（reprocess 完後跑）

```bash
cd /home/p10359945/source/repos/agentic-rag-customer-service

/home/p10359945/google-cloud-sdk/bin/gcloud compute ssh db-services \
  --zone=asia-east1-b --tunnel-through-iap \
  --project=project-4dc6cadb-5d47-4482-a32 \
  --command="docker exec agentic-rag-db psql -U postgres -d agentic_rag -tA -F '|' -c \"
SELECT d.page_number, d.id, d.filename, d.status, d.chunk_count,
       d.updated_at::text,
       COALESCE(c.chunk_index::text, ''),
       COALESCE(c.id, ''),
       COALESCE(c.content, '')
FROM documents d
LEFT JOIN chunks c ON c.document_id = d.id
WHERE d.kb_id = '559538a4-d2ac-46e8-8e2c-1d04b599d7e6'
  AND d.parent_id IS NOT NULL
  AND d.page_number IN (2, 3, 4, 6, 8, 9, 10, 11, 47, 64)
ORDER BY d.page_number, c.chunk_index NULLS FIRST;
\"" > /tmp/after_raw.txt

uv run --project apps/backend python scripts/format_dm_baseline.py \
  --input /tmp/after_raw.txt \
  --output docs/dm-baseline-and-after/after.md \
  --label after
```

### Step 5：交給 Claude diff 比對

驗收標準：
- **Page 2**：應抽出「中國信託聯名卡」「OPEN Day」「綠色商品 7% 回饋」等
  關鍵詞，**不應**再出現 baseline 那種 hallucinate 的「Francasino 自動夾
  除塵拖」「松村窯砂鍋」
- **Page 3**：應抽出「生日點數加倍」「APP 會員」具體優惠條件，不再只剩
  「【頁面分類】促銷活動頁」一句話
- **Page 8**（家樂宅 4 周年慶）：應抽出筆筆消費、新會員首購、$199 免運
  等優惠條件
- **Page 64**：應抽出「天天生鮮日 10% 現金折價券」「週二週日加油日」「週
  四豆米漿日」等每日活動，**chunk 應以活動為單位**而非偽裝成「商品：天
  天生鮮日」這種怪格式
- **Mixed 頁**：應該 **同時** 有 `## 商品段` + `## 活動段` 兩段標記

### Step 6：驗收完還原（可選）

如果新 prompt 表現滿意，KB 維持 `ocr_mode='auto'`。
若想還原（測試後想回 catalog 模式）：

```bash
/home/p10359945/google-cloud-sdk/bin/gcloud compute ssh db-services \
  --zone=asia-east1-b --tunnel-through-iap \
  --project=project-4dc6cadb-5d47-4482-a32 \
  --command='docker exec agentic-rag-db psql -U postgres -d agentic_rag -c "
UPDATE knowledge_bases SET ocr_mode = '\''catalog'\''
WHERE id = '\''559538a4-d2ac-46e8-8e2c-1d04b599d7e6'\'';
"'
```
