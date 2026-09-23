# 加密金鑰輪替 Runbook（Issue #105）

> 對象：infra 與平台負責人。金鑰內容只經 Secret Manager 傳遞，不貼進任何對話、工單或 log。

## 一、機制摘要

| 環境變數 | 內容 | 是否機密 |
|---|---|---|
| `ENCRYPTION_MASTER_KEY` | 目前**加密**用的金鑰（hex，64 字元＝AES-256） | 是（Secret Manager） |
| `ENCRYPTION_MASTER_KEY_ID` | 上面那把金鑰的 id，預設 `v1` | 否 |
| `ENCRYPTION_PREVIOUS_KEYS` | 只用來**解密**的舊金鑰，`id:hex,id:hex`，可空 | 是（Secret Manager） |

- 密文格式 `<key_id>:<base64>`。**沒有前綴的舊密文一律視為 `v1`**，所以第一把金鑰的 id 固定是 `v1`。
- active 是 `v1` 時照舊寫無前綴格式：只設 `ENCRYPTION_MASTER_KEY` 的部署與 #105 之前完全相同。
- 設定不合法時服務**拒絕啟動**，不會退回預設金鑰：hex 長度不對、id 格式不對、id 重複、active id 同時出現在 previous。錯誤訊息只含 id 與長度。
- 解密遇到設定裡沒有的 key id → 明確錯誤，訊息含該 id。

加密資料所在（`scripts/reencrypt_secrets.py` 的 `ENCRYPTED_FIELDS`，圍籬測試保證與程式一致）：

| 欄位 | 備註 |
|---|---|
| `provider_settings.api_key_encrypted` | LLM / Embedding 供應商 API key |
| `tenant_identity_secrets.secret_encrypted` | widget 宿主身分驗證密鑰 |
| `notification_channels.config_encrypted` | 通知通道設定；既有明文 JSON 會略過 |
| `bots.mcp_bindings[].env_values` | MCP registry 綁定的環境值（JSON 內層） |
| `bots.line_channel_secret`、`bots.line_channel_access_token` | LINE 憑證（#107 起 at-rest 加密，repository 層加解密） |

Redis 快取裡的密文（bot 的 LINE 憑證、LLM / Embedding 設定）不需處理：解密失敗一律當作快取未命中、回 DB 重讀。
bot 版本快照與稽核紀錄已剝除 `env_values`，不含密文（腳本最後會再數一次，應為 0）。

### LINE 憑證首次加密（#107，只做一次）

#107 上線前 LINE 憑證是明文。部署順序：

1. 先套 migration `apps/backend/migrations/alter_bots_line_credentials_text.sql`（兩欄改 TEXT，
   加密後的 access token 約 268 字元，VARCHAR(255) 放不下）。**沒套就部署，存 bot 會失敗。**
2. 部署 #107。此時舊明文照樣讀得到，之後存檔的 bot 會寫成密文。
3. 跑 `uv run python -m scripts.reencrypt_secrets --dry-run`，看「明文→密文」筆數；再不帶
   `--dry-run` 執行一次，把其餘明文轉為密文。第二次 dry-run 的「明文→密文」應為 0。

解不開的 LINE 憑證不會被當成明文吞掉：金鑰 id 不在設定中時讀 bot 直接報錯，
避免後台存檔把原憑證覆寫掉。

## 二、四步流程

以下以「`v1` → `v2`」為例。每一步都要讓**所有執行者**（Cloud Run 與 VM 上的 arq worker）
都拿到新設定、重啟完成、驗證通過，才進下一步——否則會出現「一邊寫 v2、另一邊還解不開」。

### 步驟 1：加入新金鑰（只解密，還不用它加密）

```bash
# 新金鑰本體另存一份（步驟 2 要用；也是日後回滾的來源）
openssl rand -hex 32 | tr -d '\n' \
  | gcloud secrets create rag-encryption-key-v2 --data-file=-
# previous 內容為 "v2:<新金鑰>"（首次用 create，之後用 versions add）
printf 'v2:%s' "$(gcloud secrets versions access latest --secret=rag-encryption-key-v2)" \
  | gcloud secrets versions add rag-encryption-previous-keys --data-file=-
```

`rag-encryption-previous-keys` 是新 secret：infra 要授 Cloud Run 的 run-SA `secretAccessor`，
並掛成環境變數 `ENCRYPTION_PREVIOUS_KEYS`；`ENCRYPTION_MASTER_KEY_ID` 不是機密，以一般環境變數設定。

| 設定 | 值 |
|---|---|
| `ENCRYPTION_MASTER_KEY` | 舊金鑰（不變） |
| `ENCRYPTION_MASTER_KEY_ID` | `v1`（不變） |
| `ENCRYPTION_PREVIOUS_KEYS` | `v2:<新金鑰>` |

套用：Cloud Run 起新 revision（infra 以 `gcloud run services update --update-secrets` 指向新版本）；
VM worker 更新 `.env` 後 `sudo systemctl restart arq-worker.service`。

驗證：Cloud Run `/health` 200、`systemctl is-active arq-worker` 為 active；log 沒有 `app.startup.invalid_encryption_keys`。
此步驟不改變任何資料，只是讓所有執行者先認得 v2。

### 步驟 2：切換 active

| 設定 | 值 |
|---|---|
| `ENCRYPTION_MASTER_KEY` | **新金鑰** |
| `ENCRYPTION_MASTER_KEY_ID` | `v2` |
| `ENCRYPTION_PREVIOUS_KEYS` | `v1:<舊金鑰>` |

```bash
OLD_VER=<rag-encryption-master-key 目前的版本號>
gcloud secrets versions access latest --secret=rag-encryption-key-v2 \
  | gcloud secrets versions add rag-encryption-master-key --data-file=-
printf 'v1:%s' "$(gcloud secrets versions access "$OLD_VER" --secret=rag-encryption-master-key)" \
  | gcloud secrets versions add rag-encryption-previous-keys --data-file=-
```

套用方式同步驟 1（Cloud Run 新 revision＋worker 重啟），同時把 `ENCRYPTION_MASTER_KEY_ID` 改為 `v2`。
三個值要**同一次**生效：只換了金鑰沒換 id，服務會用新金鑰去解 `v1` 密文而失敗。

驗證：
- 後台「供應商設定 → 測試連線」成功（讀的是 v1 舊密文）。
- 新建或更新一筆供應商 API key 後再測一次連線成功（寫的是 `v2:` 新密文）。
- `uv run python -m scripts.reencrypt_secrets --dry-run` 的「待轉」等於舊資料筆數、「失敗」為 0。

> ⚠️ 從這一步開始，**不可把應用程式回滾到 #105 之前的版本**：舊版不認得 `v2:` 前綴。
> 需要回滾程式碼時，只能回到含 #105 的版本（管線 3888 的 rollbackImageTag 指定 #105 之後的 `rc-<sha>`）。

### 步驟 3：重新加密既有資料

在能連到 DB、且帶有步驟 2 設定的環境執行（例如 VM worker 所在主機，`set -a && source .env && set +a` 之後）：

```bash
cd apps/backend
uv run python -m scripts.reencrypt_secrets --dry-run   # 看每個欄位的待轉筆數
uv run python -m scripts.reencrypt_secrets             # 執行（分批 commit，可中斷後重跑）
uv run python -m scripts.reencrypt_secrets --dry-run   # 應全部為 0 待轉、0 失敗
```

驗證：第二次 dry-run 的「待轉」全為 0、「失敗」為 0、快照 `env_values` 筆數為 0，指令結束碼為 0。
有失敗時會列出主鍵、欄位與 key id（不含密文）：通常是遷移前的明文或設定漏了某把金鑰，逐筆處理後重跑即可（腳本冪等）。

### 步驟 4：移除舊金鑰

| 設定 | 值 |
|---|---|
| `ENCRYPTION_MASTER_KEY` | 新金鑰 |
| `ENCRYPTION_MASTER_KEY_ID` | `v2` |
| `ENCRYPTION_PREVIOUS_KEYS` | 空 |

套用方式同上。驗證：`/health` 200、供應商測試連線成功、`--dry-run` 仍全為 0。

**舊金鑰的 Secret Manager 版本改為 disabled，不要 destroy**，保留期至少等於 DB 備份保留期：
步驟 3 之前的備份仍是 v1 密文，還原那種備份時要把 `v1:<舊金鑰>` 暫時加回 `ENCRYPTION_PREVIOUS_KEYS`。

## 三、回滾

| 時間點 | 做法 |
|---|---|
| 步驟 1 之後 | 把 `ENCRYPTION_PREVIOUS_KEYS` 清空即可（沒有任何資料用到 v2） |
| 步驟 2、3 之後 | **把 active 切回舊 id**：`MASTER_KEY=舊金鑰`、`MASTER_KEY_ID=v1`、`PREVIOUS_KEYS=v2:<新金鑰>`。v2 密文仍可解（新金鑰還在 previous）；想讓資料全回 v1 就再跑一次 reencrypt |
| 步驟 4 之後 | 先把舊金鑰從 disabled 的 Secret Manager 版本取回，放進 previous，再照上一列做 |

## 四、例行檢查

- 新增任何會寫入密文的欄位，必須登記在 `scripts/reencrypt_secrets.py`，否則
  `tests/unit/scripts/test_reencrypt_fence.py` 會紅燈。
- `infrastructure/crypto/*` 的覆蓋率下限 95%（`scripts/check_coverage_floors.py`）。
