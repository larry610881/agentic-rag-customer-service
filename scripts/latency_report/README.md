# LINE 延遲分析報告產生器

產出 `LINE延遲分析_<日期>.xlsx`（總覽 / 圖表 / 每筆請求明細 / 階段統計 / Webhook計時 / 優化歷程），
用於向使用者說明 LINE AI 客服回應時間的組成與優化成果。Issue #49。

## 重產步驟（有新數據時，例如補測 Haiku 樣本、TTFT 上線後）

```bash
cd scripts/latency_report

# 1. 匯出 DB trace 逐階段拆解（dev-vm，需 pic.aiagent gcloud 帳號）
B64=$(base64 -w0 query.sql)
gcloud compute ssh db-services --zone=asia-east1-b --tunnel-through-iap \
  --project=project-4dc6cadb-5d47-4482-a32 \
  --command="echo $B64 | base64 -d | docker exec -i agentic-rag-db psql -U postgres -d agentic_rag --csv" \
  2>/dev/null > traces.csv

# 2. 匯出 Cloud Run webhook 計時 log
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.event="line.webhook.timing"' \
  --project=project-4dc6cadb-5d47-4482-a32 --limit=200 --freshness=14d \
  --format='csv(timestamp,jsonPayload.llm_model,jsonPayload.process_message_ms,jsonPayload.reply_ms,jsonPayload.persist_ms,jsonPayload.total_ms,jsonPayload.answer_len)' \
  > webhook_timing.csv

# 3. 產表 + 加圖表（openpyxl 在 backend venv 內）
cd ../../apps/backend
uv run python ../../scripts/latency_report/build_excel.py
uv run python ../../scripts/latency_report/append_charts.py
```

## 待辦（下次更新時要做）

- [ ] 補入 Haiku 4.5 多筆樣本後的 P3 統計（2026-07-21 時僅 1 筆首測）
- [ ] TTFT（`first_token` trace 節點，commit 於 Issue #49）上線後，
      在 query.sql 加入 first_token 欄位 → 圖表加「web 首字 vs LINE 完整回覆」對比
- [ ] 檔名日期與 build_excel.py 內的階段切分時間（P0~P3 cutoff）需隨資料期間調整

## 注意

- 階段分期（P0 基準 / P1 回覆先行 / P2 關閉推理 / P3 Haiku分級）的切分時間
  寫死在 `build_excel.py` 的 `classify()`，以 2026-07-21 的部署/設定變更時間為準
- `webhook_timing.csv` 的 llm_model 欄是 bot 預設值，worker 覆寫不反映；實際模型以 traces 為準
- 圖表配色為 dataviz 驗證過的 categorical palette（藍/綠/洋紅/黃），勿隨意更換
