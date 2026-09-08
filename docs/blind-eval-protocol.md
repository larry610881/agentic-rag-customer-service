# 盲評作業程序（模型評測用）

目的：讓另一個 session（例如換成 Fable 5）在**完全不知道哪個回答來自哪個模型**的情況下
評分，避免評分者對品牌的先驗影響結果。

---

## 一、為什麼不能在專案資料夾裡評

在 `~/source/repos/agentic-rag-customer-service` 底下開 session，這些東西會自動進上下文，
每一項都足以直接洩底：

| 來源 | 洩漏什麼 |
|------|---------|
| 專案記憶 `~/.claude/projects/-home-p10359945-source-repos-agentic-rag-customer-service/memory/` | 整個評測企畫、跑了哪些模型、RunPod pod、已知的優劣 |
| 專案 `CLAUDE.md` 與 `.claude/rules/` | 專案脈絡 |
| `git log` / `git status` | commit 訊息直接寫著 `qwen3.8:27b-q8_0`、`gemini-3.8-flash` |
| `scripts/local_model_eval/results/*.jsonl` | 原始檔的 `bot` 欄位就是模型名 |
| 檔名 | `quick20_評測_gpt-5.6-terra_*.jsonl` |

Claude Code 的記憶是**以工作目錄為單位**（`~/.claude/projects/<路徑編碼>/memory/`），
所以只要換一個從未用過的目錄，就是一份全新的空記憶。

## 二、在哪裡開

```
~/qa-scoring
```

選它的理由：

- 在 `~` 底下，**不在 `~/source/repos` 這個 hub 裡**，也不在任何 git repo 內
  （`~` 本身不是 git repo，已確認），所以沒有 git 歷史可翻。
- 從未當過工作目錄 → 對應的 `~/.claude/projects/-home-p10359945-qa-scoring/memory/` 是空的。
- 目錄名中性。工作目錄名稱本身會出現在 session 的系統提示裡，取名成
  `local-model-eval` 之類的等於自己破功。
- 全域 `~/.claude/CLAUDE.md` 一定會載入，但它只有通用開發規範，沒有任何模型名或本次評測資訊
  （已確認）。

盲評包由 `make_blind_packet.py` 產生，內容只有：

```
~/qa-scoring/
├── README.md      作業說明與評分標準
├── 答案/          每段對話一個 .md：使用者問題、參考答案、數個匿名回答
└── 評分表.csv     待填
```

**對照表不在裡面**，寫在專案的 `scripts/local_model_eval/results/blind_key_*.json`。

## 三、匿名怎麼做的

1. **每一輪各自獨立洗牌**。同一個模型在 `E1-1` 可能是「甲」，到 `E1-2` 變成「丙」。
   這是關鍵：評分者就算從文風看出「這兩段像同一個系統寫的」，也沒辦法把它綁到一個固定代號，
   跨題累積指紋這條路被切斷。要聚合回每個模型的成績只能靠對照表。
2. **刪掉所有非文字訊號**。延遲、token 數、`model` 欄位、來源檔名、conversation_id
   一律不進盲評包 —— 地端模型明顯較慢、token 分布也不同，留著等於直接標答案。
3. **遮蔽自我指涉字串**。回答裡若出現 `gemini` / `gpt-x` / `openai` / `qwen` / `通義` /
   `claude` / `anthropic` / `ollama` / `大型語言模型` 等，換成 `[已遮蔽]`。
4. **出貨前自動掃描**。產檔後掃過盲評包每個檔案，只要還有洩漏字串就**刪掉整包並中止**，
   不會產出半成品。

殘留風險（誠實說）：文風與排版習慣仍可能被有經驗的評分者辨認出「這幾個是同一家」，
只是無法對應到具體品牌，也無法跨輪累積。要再降風險就得做格式正規化，但那會毀掉
「格式與繁體」這個評分維度，得不償失。

另外，這次四個候選裡**沒有 Claude**，所以不存在評分者認出自己輸出的問題。

## 四、操作步驟

**1）產盲評包**（在專案資料夾做）

`--results` 收**多個檔**：一天下來資料是分批產生的（不同臂在不同時間跑、修完 bug 重跑），
硬要合成單一檔反而容易把修復前後的資料混在一起。

```bash
cd ~/source/repos/agentic-rag-customer-service
python3 scripts/local_model_eval/make_blind_packet.py \
  --results scripts/local_model_eval/results/main60_20260908-1849.jsonl \
            scripts/local_model_eval/results/main60_20260908-1942.jsonl \
            scripts/local_model_eval/results/main60_20260908-2056.jsonl \
  --out-dir ~/qa-scoring \
  --key-file scripts/local_model_eval/results/blind_key_20260908.json
```

### 重跑要評幾次？`--runs`

跑 3 輪是為了量穩定度，但**不代表 3 輪都要送去盲評**：

| 模式 | 待評回答數（本次資料） | 適用 |
|---|---|---|
| `all` | 180 輪 × 5 = **900** × 3 維度 = 2,700 個判斷 | 幾乎不可行，評到後面品質必掉 |
| `first` | 60 輪 × 5 = 300 | 可行，但「某臂第一輪剛好手氣好」會直接變成結論 |
| `random`（**預設**） | 60 輪 × 5 = 300 | 每輪各自抽一次重跑，樣本量一樣但分散在三次上 |

`random` 用的是**分層**而不是純隨機：把題目順序打亂後輪流指派重跑編號，
確保三次重跑被抽到的次數相同（本次 20/20/20）。純 `rng.choice` 在 60 次抽樣下很容易歪掉
（實測 seed 20260908 抽出 26/25/9，等於第三次重跑幾乎沒被評到，白花了跑三輪的成本）。

產包後可以自己驗一次洗牌有沒有生效——每個模型應該平均散落在所有代號上：

```bash
python3 -c "
import json,collections
k=json.load(open('scripts/local_model_eval/results/blind_key_20260908.json',encoding='utf-8'))
c=collections.defaultdict(collections.Counter)
for cell,l2b in k['mapping'].items():
    for lab,bot in l2b.items(): c[bot][lab]+=1
for bot,cnt in sorted(c.items()): print(bot, dict(sorted(cnt.items())))
print('重跑分布', dict(collections.Counter(x.split('-r')[-1] for x in k['mapping'])))
"
```

若某個模型集中在一兩個代號，代表洗牌壞了，**不要送去評**。

**2）開盲評 session**

```bash
cd ~/qa-scoring
claude
```

- **開全新 session**，不要 `--continue` / `--resume`，那會把舊上下文帶進來。
- 第一句就照著 `README.md` 講，例如：
  > 讀 README.md 跟 答案/ 底下所有檔案，依 README 的標準逐輪評分，把分數填進 評分表.csv。

**這幾句不要說**（都會直接或間接洩底）：

- 「這是模型評測」「比較地端跟雲端」「哪個是 Qwen」
- 「這是我們 RAG 專案的結果」
- 任何指向 `~/source/repos/...` 的路徑

**3）揭盲與聚合**（回到專案資料夾）

```bash
python3 scripts/local_model_eval/unblind_scores.py \
  --scores ~/qa-scoring/評分表.csv \
  --key-file scripts/local_model_eval/results/blind_key_<日期>.json \
  --results scripts/local_model_eval/results/main60_<時間>.jsonl
```

輸出各模型三個維度的平均、依難度層的分數、失分最重的輪次，以及延遲／token
（效能數據不參與評分，揭盲後才拿來對照）。

## 五、評分完的檢查

- [ ] `評分表.csv` 沒有空欄（`unblind_scores.py` 會回報被略過的列數）
- [ ] 抽查 3–5 輪，確認評分者理解「該拒答的題目編出答案要給 0 分」
- [ ] 各模型輪數相同（不同代表有輪次漏評）
- [ ] 分數若呈現「某代號全部偏高」，檢查是不是洗牌沒生效（正常情況下代號與分數無關）
