# NotebookLM 生成 Prompt

> 搭配 `notebooklm-podcast.md` 和 `notebooklm-ppt.md` 使用。

---

## Podcast（Audio Overview）

NotebookLM 的 Podcast 功能叫 **Audio Overview**，在 Notebook 右側面板。它有一個 "Customize" 欄位可以下指示：

```
請用繁體中文進行對話。目標聽眾是企業客戶（非技術人員），
他們正在評估是否要導入 AI 客服。

語氣輕鬆專業，像兩位科技 Podcast 主持人在聊一個他們覺得很酷的產品。
用具體場景帶入功能（例如餐廳老闆、電商客服主管的日常痛點），
避免講太多技術術語。

重點放在：
1. 為什麼傳統客服有問題
2. RAG 為什麼讓 AI 客服不會亂掰
3. 一行程式碼嵌入網站有多簡單
4. LINE 整合對台灣市場的意義
5. 管理者怎麼監控和改善 AI 表現

不要提成本數字、ROI、競品比較。
```

---

## PPT（Briefing Doc / Study Guide）

NotebookLM 沒有直接生成 PPT 的功能，但可以用以下方式產出適合做 slides 的內容：

### 方式 1 — 用 "Briefing Doc" 功能

右側面板 → Briefing Doc，不需要額外 prompt，它會自動從文件提取結構化摘要。

### 方式 2 — 在 Chat 裡下 prompt

```
請根據來源資料，產出一份 15 張投影片的大綱。
每張 slide 包含：
- 標題
- 3-5 個重點（每個重點一行，不超過 20 字）
- 講者備註（2-3 句話的口語化說明）

目標聽眾：企業決策者，非技術背景。
語言：繁體中文。
不要提成本、ROI、競品比較。
```

### 方式 3 — 要求產出 Markdown 表格格式

方便直接貼進 PPT 工具：

```
請根據來源資料，用 Markdown 表格整理每張投影片的內容：
| Slide # | 標題 | 重點 1 | 重點 2 | 重點 3 |

控制在 15 張以內，每個重點不超過 20 字。繁體中文。
```

---

## 操作步驟

1. 到 [NotebookLM](https://notebooklm.google.com) 建立 Notebook
2. **Podcast**：上傳 `notebooklm-podcast.md` → Audio Overview → Customize → 貼上 prompt → Generate
3. **PPT**：另建一個 Notebook，上傳 `notebooklm-ppt.md` → 在 Chat 裡貼 prompt

兩份分開做效果比較好，因為混在一起 NotebookLM 會搞混風格。
