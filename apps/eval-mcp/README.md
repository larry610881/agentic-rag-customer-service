# eval-mcp —— 評測用自架 MCP 伺服器

三個**確定性**工具，給模型評測的工具呼叫題組用。

## 為什麼自架，不串現成的開源 MCP

評測要的是可重現。第三方 MCP 有網路抖動、限流與回應變動，模型明明選對工具卻拿到逾時，
分數會掉在跟模型能力無關的地方。這裡的工具回傳固定資料，同一輸入永遠同一輸出，
**工具選對與否是唯一的變因**。

（要做**展示**而不是評測，再去串真的 fetch / 搜尋 / 天氣類 MCP，但建議用不同的 bot。）

## 三個工具各自製造一種難度

| 工具 | 回傳 | 為什麼放它 |
|------|------|-----------|
| `get_today` | 今天日期、星期、台北時間、當期 DM 檔期與剩餘天數 | 讓「這期 DM 還剩幾天」變成**必須「DM 圖卡工具 + 本工具」兩個一起用**才算得出來的多工具題 |
| `get_store_hours` | 七家分店的營業時間 | 跟 `rag_query` **高度重疊的干擾項**——營業時間知識庫也查得到，看模型會不會被工具名稱吸引而放棄檢索 |
| `get_order_status` | 三筆假訂單的狀態、金額、付款方式 | 讓「帳單金額對不上」的正解從「轉真人」變成「查訂單」。**同一題在有無此工具時正解不同**，這是測「工具感知」最乾淨的設計 |

## 認證方式與它的限制

後端的 MCP client 是 `streamablehttp_client(url)`，**不送自訂 header**
（`discover_mcp_server_use_case.py:90`），所以無法用 Bearer token 或 Cloud Run IAM 認證。
唯一可行的是把密鑰放在**網址路徑**：服務掛載於 `/<MCP_PATH_TOKEN>/mcp`。

這裡的工具全是唯讀假資料，路徑密鑰足夠。**真要接敏感資料的 MCP，必須先讓 client 支援
header 認證**，否則等於把端點公開。

## 部署（要有建立 Cloud Run 服務權限的人執行）

映像已建好並推上 Artifact Registry：
`asia-east1-docker.pkg.dev/project-pic-ai-innovation-poc/poc-ar-rag/eval-mcp:v1`

```bash
# 產一個路徑密鑰（或用你自己的）
TOKEN=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
echo "路徑密鑰：$TOKEN"   # 記下來，註冊 MCP 時要用

gcloud run deploy eval-mcp \
  --image=asia-east1-docker.pkg.dev/project-pic-ai-innovation-poc/poc-ar-rag/eval-mcp:v1 \
  --region=asia-east1 --project=project-pic-ai-innovation-poc \
  --platform=managed --allow-unauthenticated --port=8080 \
  --memory=512Mi --cpu=1 --min-instances=0 --max-instances=2 \
  --set-env-vars="MCP_PATH_TOKEN=$TOKEN"
```

驗證：

```bash
URL=$(gcloud run services describe eval-mcp --region=asia-east1 \
  --project=project-pic-ai-innovation-poc --format='value(status.url)')
curl -s "$URL/health"      # → {"status":"ok","tools":[...]}
echo "MCP 端點：$URL/$TOKEN/mcp"
```

> `--min-instances=0`：沒人用就不計費，代價是冷啟動約 2–3 秒。評測時要量延遲的話，
> 跑題前先打一次 `/health` 暖機，或臨時設成 1。

## 註冊進平台

部署完把網址給我，我用 `scripts/register_eval_mcp.py` 一次做完：探索工具 → 註冊到
MCP registry（scope 限評測租戶）→ 掛進工具評測用的 bot。

也可以在後台手動：平台設定 → MCP Servers → 新增，transport 選 `http`、url 填
`https://.../<TOKEN>/mcp`，按「探索」後三個工具會自動帶出來。

## 本機跑

```bash
MCP_PATH_TOKEN=localtest python main.py     # → http://127.0.0.1:8080/localtest/mcp
```
