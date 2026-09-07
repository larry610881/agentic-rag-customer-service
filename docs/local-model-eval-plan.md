# 地端模型評測支線企畫（Qwen 3.8 / 3.6 × GPT-5.1 / Gemini 3.8 Flash）

> 日期：2026-09-04　狀態：v0.1 草案，待 Larry 拍板 §7 待決事項後開 Issue
> 支線名稱建議：`feature/local-model-eval`
> 相關：`docs/llm-model-selection.md`（2026-03，排除大陸廠商模型）、`scripts/runpod_ctl.py`、
> `scripts/latency_report/`（既有題組與延遲報表）、`application/eval_dataset/`（評測集 + assertions）、
> `application/prompt_gate/replay_use_cases.py`（真實流量回放）

---

## 0. 一句話結論

**先測 Qwen3.6-35B-A3B（速度）與 Qwen3.8-27B（品質）兩個開源模型，在 RunPod 租 L40S 48GB（US$0.99/hr）跑 vLLM FP8，
用既有 10 題組 + 攻擊題組 + 工具題組對 GPT-5.1 與 Gemini 3.8 Flash 做五組案例對比；整個評測期 GPU 費用約 US$80–120（約 NT$2,600–4,000）。**
地端在 POC 流量下**不會比 API 省錢**（損益平衡約每月 15–30 萬輪對話），它的價值是**延遲槓桿**（分類器 1.5s → 0.5s）與**資料不出境／客戶地端部署**（UMC VMS 這類內網案）。

---

## 1. 背景與目標

### 1.1 為什麼回頭測地端

| 動機 | 現況數據 | 地端能改變什麼 |
|------|---------|---------------|
| 延遲 | 5.1s 基線 = 非 LLM 1.0 + 分類 1.5 + 生成 2.6（planning-context 09-03） | 分類器改地端小模型目標 <0.5s；3B-active MoE 生成 300 token 約 1.5s |
| 資料落地 | UMC VMS 內網隔離、金融／製造客戶要求資料不出境 | 「agent 平台 + 地端模型」是 B 版 deck 的服務前提 |
| 供應商風險 | Gemini 3.8 Flash 2027-01-01 起漲價一倍（$0.75→$1.5 / $3.75→$7.5） | 手上有可切換的地端選項才有議價空間 |
| 3D 展備案 | #70 kb 模式 + JSON 輸出，目前規劃 Gemini 3.7 Flash 單模型 | 驗證地端模型的 JSON schema 遵從度，作為展場斷網備案 |

### 1.2 目標與非目標

- **目標 A**：回答「Qwen 3.8 還是 3.6、哪個尺寸」——用數據而非規格書。
- **目標 B**：產出一張「模型 × 案例組」的對比矩陣（品質／延遲／每輪成本／維運），可直接放進 sales deck A-11 方案表與 B-13 服務商品頁。
- **目標 C**：留下可重跑的評測腳本，之後換模型（Qwen 4、Gemini 4）只改設定。
- **非目標**：本支線不做地端正式部署、不做微調（fine-tune）、不改對話管線邏輯（channel-parity 紅線）。

---

## 2. 模型選擇：Qwen 3.8 vs 3.6

### 2.1 兩代陣容（開源權重）

| 模型 | 架構 | 總參數 / 啟用 | 上下文 | 授權 | 單卡可跑？ | 備註 |
|------|------|--------------|--------|------|-----------|------|
| **Qwen3.8-27B** | Dense | 27.8B / 27.8B | 262K | Apache 2.0 | ✅ FP8 28GB / 4-bit 16GB | 內建視覺、`reasoning_effort` 統一旋鈕（不再分 Thinking 版）、SWE-bench Pro 61.7 |
| Qwen3.8-Flash-Next | 超稀疏 MoE | 125B（含 51B n-gram 表 ≈176B）/ 6B | 262K | qwen-community-1.0 | ❌ 需多卡 | vLLM day-0 支援；託管 API $0.15/$0.47 最便宜 |
| Qwen3.8-2.4T-A95B / Max | MoE | 2.4T / 95B | 1M | 自訂 | ❌ | 不在考慮範圍 |
| **Qwen3.6-35B-A3B** | MoE | 35B / 3B | 262K | Apache 2.0 | ✅ FP8 38GB / 4-bit 23GB | **解碼最快**（MTP 開啟約 220–240 t/s 單流）；3.8 世代**沒有**對應的中型 MoE |
| Qwen3.6-27B | Dense | 27B / 27B | 262K | Apache 2.0 | ✅ 同 3.8-27B | 已被 3.8-27B 取代，只在 3.8 有推理引擎相容問題時當備胎 |

> 3.8 世代的官方升級路徑：35B-A3B 的「預期後繼」是 3.8-27B——參數更少但是 dense，**速度會退**。
> 這正是本評測要回答的核心取捨：**3.6-35B-A3B 的速度 vs 3.8-27B 的品質**。

### 2.2 對應我們的三種工作負載

| 管線步驟 | 需求 | 首選 | 次選 | 理由 |
|---------|------|------|------|------|
| 意圖分類 / 攻擊閘門 | <0.5s、輸出十幾個 token、non-thinking | **3.6-35B-A3B**（non-thinking） | 3.8-27B non-thinking | 3B active 的 prefill + 短輸出最快；分類不需要 27B 的推理深度 |
| 快速道 RAG 生成 | 300 token 中文、忠於檢索、無 `**` | **3.6-35B-A3B** | 3.8-27B | 300 token @ 220 t/s ≈ 1.4s；27B @ 60–120 t/s ≈ 2.5–5s |
| ReAct 工具呼叫（深度模式） | 工具選對、參數正確、不裸吐工具名 | **3.8-27B** | 3.6-35B-A3B | 3.6 文件已註明 tool calling 巢狀物件解析改善；3.8 再進一步，dense 模型工具穩定度通常較高 |
| kb 模式 JSON 輸出（#70） | schema 遵從 | 兩者都測 | — | vLLM 的 guided decoding（`response_format` json_schema）兩者皆可用，能力表填 `native_schema` 前要實測 |

**結論：兩個都測，不是二選一。** 若只能測一個，先測 **3.6-35B-A3B**——它直接對應延遲目標，且 3.8 世代沒有替代品。

### 2.3 參數量／量化／GPU 對應

| 模型 × 精度 | 權重 VRAM | 建議 GPU（RunPod） | 單流解碼估計 | 適用 |
|------------|----------|------------------|-------------|------|
| 35B-A3B **FP8** | ~38GB | L40S 48GB / A100 80GB | 200+ t/s | 主力評測組 |
| 35B-A3B 4-bit（AWQ/GGUF） | ~23GB | RTX 5090 32GB / 4090 24GB | 150–200 t/s | 省錢組，品質要對照 FP8 |
| 27B **FP8** | ~28GB | L40S 48GB / RTX 5090 32GB（KV 空間緊） | 60–120 t/s（含 MTP） | 主力評測組 |
| 27B BF16 | ~56GB | A100 80GB / H100 | 40–70 t/s | 品質基準（確認 FP8 沒掉分） |
| 27B 4-bit | ~16GB | RTX 4090 24GB | 80–110 t/s | 客戶端單張消費卡情境 |

> VRAM 只算權重；KV cache 另加（262K 上下文全開會爆，評測時 `--max-model-len 16384` 即可）。
> t/s 為單流估計，取自 Unsloth / vLLM 社群數據（RTX 5090 / RTX 6000 / B200），L40S 記憶體頻寬較低要打折。

---

## 3. 對比設計

### 3.1 對照臂（arms）

| # | 臂 | 接法 | 用途 |
|---|----|------|------|
| B1 | **GPT-5.1**（或 POC 現用 gpt-5.4，待決） | 既有 openai provider | 品質上限基準；$1.25 / $10 per M |
| B2 | **Gemini 3.8 Flash**（thinking 最低） | 既有 google provider（OpenAI 相容端點） | 成本／延遲基準；$0.75 / $3.75（2026 年底前） |
| L1 | Qwen3.6-35B-A3B FP8 @ L40S | ollama provider `base_url` 指向 RunPod vLLM | 速度組 |
| L2 | Qwen3.8-27B FP8 @ L40S | 同上 | 品質組 |
| L3（選配） | Qwen3.8-27B BF16 @ A100 80GB | 同上 | 驗 FP8 是否掉分，只跑品質題組 |
| L4（選配） | 35B-A3B 4-bit @ RTX 5090 | 同上 | 客戶端消費卡可行性 |

每臂固定：`temperature 0.7 / top_p 0.8 / top_k 20 / presence_penalty 1.5`（Qwen non-thinking 官方建議），
GPT／Gemini 用各自預設但 reasoning 設最低（#72 已把 `reasoning_effort=none` 接通三通路）。

### 3.2 五組案例（怎麼開）

案例全部從**既有資產**抽，不新編題，避免「為地端模型量身訂做」的偏誤。

| 組 | 題數 | 來源 | 金標準 | 指標 | 通過線 |
|----|------|------|--------|------|--------|
| **C1 分類／閘門** | 40 | 4 worker 各 8 題 + `prompt_attack_cases_2026-08-17.md` 8 題攻擊 | worker 名 / `attack` 標籤（人工標） | 準確率、攻擊召回率、p50/p90 延遲 | 準確率 ≥ 現行分類器、攻擊召回 8/8、p90 <0.6s |
| **C2 快速道 RAG** | 30 | `test_10_questions` 10 題 + `test_10_carrefour` 10 題 + 從 `uni-prosperity-faq-data.json` 抽 10 題 | FAQ 原文 | 忠實度（LLM judge，既有 assertions）、正確性人工抽檢、無 `**`、長度 ≤200 字、回覆完整時間 | judge ≥ B2 的 95%、10 題中 ≥8 題 ≤4s |
| **C3 工具呼叫** | 20 | 轉真人 5、DM 圖卡 5、示範商店查訂單／退貨 RMA 10（demo 十題候選 #1） | 預期工具 + 參數 | 工具選對率、參數正確率、裸吐工具名次數 | 選對 ≥ 90%、裸吐 0 |
| **C4 JSON 輸出** | 15 | 3D 展兩個 prompt（純文字版／JSON 版）+ 自訂 schema 5 題 | schema | schema 通過率、miss_reply 觸發正確 | 通過 ≥ 95% |
| **C5 真實流量回放** | 50 | 閘門 replay（`replay_use_cases.py`）抽 POC 或家樂福 LINE trace 50 筆 | 原回覆 | 與原回覆 judge 對比、延遲分佈 | 不劣於原回覆 90% |

每題**跑 3 次**取中位數（生成式輸出單次不算數，見 Code Review 準則）。

### 3.3 輸出：對比矩陣

| 模型 | C1 準確 / p90 | C2 judge / p50 | C3 選對率 | C4 schema | C5 | 每輪成本 | 維運 |
|------|--------------|----------------|-----------|-----------|----|---------|------|
| GPT-5.1 | | | | | | US$0.0049 | 無 |
| Gemini 3.8 Flash | | | | | | US$0.0023（2027：0.0045） | 無 |
| Qwen3.6-35B-A3B FP8 | | | | | | 固定 US$723/月 ÷ 輪數 | vLLM + GPU |
| Qwen3.8-27B FP8 | | | | | | 同上 | 同上 |

（每輪成本假設 1,500 input + 300 output token；固定月費 = L40S 24×7。）

---

## 4. 執行方式

### 4.1 架構接法（零管線修改）

1. RunPod 起 vLLM 容器（`vllm/vllm-openai:latest`），開 `--served-model-name`、`--quantization fp8`、`--enable-auto-tool-choice --tool-call-parser <依模型版本>`、`--max-model-len 16384`。
2. `OLLAMA_BASE_URL` 指向 pod 的 proxy URL（`dynamic_llm_factory.py` 第 237–241 行：ollama provider 讀 `Settings.ollama_base_url` 並自動補 `/v1`，走 OpenAI 相容協定，vLLM 直接吃，**不用改程式**）。工具呼叫要開 vLLM 的 `--enable-auto-tool-choice`，parser 依 Qwen 3.6/3.8 版本的官方建議選（hermes 或 qwen 專用 parser），啟動時實測。
3. Bot 層：`llm_model = "ollama:Qwen3.6-35B-A3B"`；分類器層：`router_model = "ollama:..."`（既有 `intent_classifier.py` 已支援 `router_model` 覆寫）。
4. 每個臂建一個 bot（同 KB、同 prompt、同 workers），跑同一份題組——**通路對等**：走 `/api/v1/agent/chat`，不碰 LINE 專用路徑。

### 4.2 工作分解

| 步驟 | 產出 | 估時 |
|------|------|------|
| S0 Issue + 分支 | `feature/local-model-eval`、Issue（enhancement） | 0.5h |
| S1 題組整理 | `scripts/local_model_eval/cases/c1..c5.json`（含金標準） | 0.5 天 |
| S2 評測腳本 | `scripts/local_model_eval/run_bench.py`：多臂 × 題組 × 3 次 → CSV；`build_report.py` 重用 latency_report 的 xlsx 產表 | 1 天 |
| S3 RunPod 環境 | pod 模板（vLLM 指令、network volume 放權重）、`runpod_ctl.py` 加 `create` 子命令 | 0.5 天 |
| S4 跑 L1/L2 + B1/B2 | 四臂數據 | 1 天（GPU 開著約 8h） |
| S5 選配 L3/L4 | 兩臂數據 | 0.5 天（GPU 4h） |
| S6 報告 | 對比矩陣 + 建議 + deck 用一頁 | 0.5 天 |

合計約 **4–5 個工作天**；GPU 實際開機約 12–16 小時。

### 4.3 風險

- **vLLM 對 Qwen3.8 hybrid attention 的支援**：新架構（Gated DeltaNet + QSA）在 L40S（Ada）上的 kernel 成熟度未知；若 3.8-27B 起不來，先用 3.6-27B 佔位，不阻塞 35B-A3B。
- **RunPod 區域延遲**：多數機房在美歐，台灣打過去 RTT +150–200ms；分類器 <0.5s 的目標要扣掉這段，報告分開列「模型時間」與「端到端時間」。
- **中文品質**：Qwen 中文原生強，但繁體用語（「門市」「發票載具」）需人工抽檢，不能只看 judge 分。

---

## 5. GPU 租用費用估算

### 5.1 單價（RunPod Secure Cloud，2026-07/08 查證，按秒計費）

| GPU | VRAM | US$/hr | 能跑什麼 |
|-----|------|--------|---------|
| RTX 4090 | 24GB | 0.69 | 4-bit 27B / 4-bit 35B-A3B（緊） |
| **RTX 5090** | 32GB | 0.99 | FP8 27B（KV 緊）、4-bit 35B-A3B；Blackwell FP8/NVFP4 快 |
| **L40S** | 48GB | 0.99 | FP8 兩者皆可，**評測主力** |
| A100 80GB | 80GB | 1.39 | BF16 兩者皆可，品質基準 |
| H100 PCIe | 80GB | 2.89 | 只在做並發壓測時用 |

GCP asia-east1 對照：L4 24GB US$0.70/hr（頻寬低、只適合 4-bit，太慢）、A100 40GB US$3.67/hr、A100 80GB US$5.03/hr，Spot 可省 60–90% 但會被搶。**評測期用 RunPod，正式地端才考慮 GCP 台灣區或客戶自備。**

### 5.2 評測期預算

| 項目 | 計算 | US$ |
|------|------|-----|
| L1 + L2 主力（L40S） | 8h × 0.99 × 2 臂 | 16 |
| L3 品質基準（A100 80GB） | 4h × 1.39 | 6 |
| L4 消費卡（RTX 5090） | 4h × 0.99 | 4 |
| 環境建置 / 除錯 / 下載權重 | 6h × 0.99 | 6 |
| 並發壓測（H100，選配） | 2h × 2.89 | 6 |
| Network volume 150GB 放權重 | 0.07 × 150 × 1 月 | 11 |
| 雲端 API 對照臂（B1/B2） | 155 題 × 3 次 × 2 臂 × ~2k token | <2 |
| **小計** | | **≈ 51** |
| **含 2× 緩衝（重跑、踩坑）** | | **≈ 80–120（NT$2,600–4,000）** |

### 5.3 若之後真的上線（月費，供 deck 用）

| 方案 | 月費 US$ | 折 NT$（×32） | 損益平衡 vs GPT-5.1 | vs Gemini 3.8 Flash（2026 / 2027 價） |
|------|---------|-------------|-------------------|------------------------------------|
| L40S 24×7 單卡 | 723 | 23,000 | ≈ 148k 輪/月 | ≈ 320k / 160k 輪/月 |
| A100 80GB 24×7 | 1,015 | 32,500 | ≈ 207k 輪/月 | ≈ 450k / 225k 輪/月 |
| Community Cloud / Spot | 上列 5–7 折 | | | |

POC 與首批客戶月流量遠低於此，**地端的賣點只能是「資料不出境／內網部署／延遲」，不能講省錢**；月流量破 20 萬輪的客戶才進入成本論述。

---

## 6. 交付物

1. `docs/local-model-eval-plan.md`（本文件）→ 拍板後改成 `docs/local-model-eval-report.md` 填數據
2. `scripts/local_model_eval/`：題組 JSON、`run_bench.py`、`build_report.py`、RunPod vLLM 啟動說明
3. 對比矩陣 xlsx + deck 一頁（A-11 方案表「地端選項」欄、B-13 服務商品「地端落地」）
4. `docs/llm-model-selection.md` 補「地端／開源」章節（現版本排除 Qwen，要註明「地端權重 ≠ 大陸雲端 API」的政策解讀）

---

## 7. 待 Larry 決定

1. **大陸模型政策**：`llm-model-selection.md`（03-15）排除 Qwen；本支線用的是 Apache 2.0 權重跑在我們的 GPU，資料不經阿里雲。這個解讀是否可對客戶講？若公司政策連權重都不行，替代開源選項是 Gemma / Llama / Mistral 系（品質與中文需另評）。
2. **GPT 基線用 5.1 還是 5.4**：POC LINE bot 現跑 gpt-5.4；deck 對比若寫 5.1 要一致。
3. **RunPod 帳號**：`runpod_ctl.py` 需要 `RUNPOD_API_KEY`，是舊帳號還是重開；預算上限 US$120 是否 OK。
4. **評測範圍**：只做 C1 分類器（最小、最快見效）還是 C1–C5 全做（本文件預設全做）。
5. **3D 展是否納入**：C4 JSON 組是為展場備案設計，若展覽確定用 Gemini 3.7 Flash 單模型，C4 可降為選配。
6. **地端 Qwen 託管 API（Flash-Next $0.15/$0.47）要不要當第三對照**：最便宜但資料進阿里雲，依第 1 點政策決定。

---

## 8. 來源

- Qwen 3.8 陣容與規格：[codersera 陣容整理](https://codersera.com/blog/qwen-3-8-model-lineup-2026/)、[Yotta Labs 27B 硬體需求](https://www.yottalabs.ai/post/qwen-3-8-27b-specs-hardware-requirements-how-to-run-2026)、[HF Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)、[vLLM Flash-Next day-0](https://x.com/vllm_project/status/2092600887873286157)、[MarkTechPost Flash-Next](https://www.marktechpost.com/2026/08/26/alibabas-qwen-team-releases-qwen3-8-flash-next-a-125b-multimodal-moe-with-6b-active-parameters-previewing-the-qwen4-architecture/)
- Qwen 3.6 規格與 VRAM：[Unsloth Qwen3.6 文件](https://unsloth.ai/docs/models/qwen3.6)、[HF Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)、[Qwen 官方 3.6-27B 部落格](https://qwen.ai/blog?id=qwen3.6-27b)
- 27B 實測吞吐：[fentz26 RTX 5090 vLLM 筆記](https://github.com/fentz26/Qwen3.8-27B-5090/tree/main)、[syv-ai RTX 3090 筆記](https://github.com/syv-ai/qwen38-27b-rtx3090)
- 雲端 API 定價：[OpenAI Pricing](https://developers.openai.com/api/docs/pricing)、[GPT-5.1 定價整理](https://chatlyai.app/blog/gpt-5-1-pricing-explained)、[Gemini 3.8 Flash 定價（apidog）](https://apidog.com/blog/gemini-3-8-flash-pricing/)、[OpenRouter gemini-3.8-flash](https://openrouter.ai/google/gemini-3.8-flash)
- GPU 租用：[RunPod Pricing](https://www.runpod.io/pricing)、[Northflank RunPod 價格拆解](https://northflank.com/blog/runpod-gpu-pricing)、[Google Cloud GPU pricing](https://cloud.google.com/products/compute/gpus-pricing)、[Thunder Compute GCP GPU 整理](https://www.thundercompute.com/blog/google-cloud-gpu-instances)
