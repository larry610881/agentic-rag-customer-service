# 企業級 RAG 聊天機器人 — 反饋系統設計

> 目標：建立完整的反饋閉環，從收集、儲存、分析到迭代改善，支援多通路（Web / LINE Bot）。

---

## 1. 系統架構總覽

```
┌─────────────────────────────────────────────────────────────────┐
│                        反饋收集層                                │
│                                                                 │
│   Web Chat UI          LINE Bot              營運後台            │
│   👍👎 按鈕            Quick Reply           人工標註            │
│   評分卡片              Postback Event        批次匯入            │
│   文字追問              Flex Message                             │
└──────────┬─────────────────┬────────────────────┬───────────────┘
           │                 │                    │
           ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        反饋儲存層                                │
│                                                                 │
│   PostgreSQL                        Redis                       │
│   ├── conversations     (永久)      ├── session context (即時)   │
│   ├── messages          (永久)      └── TTL 24h                 │
│   ├── feedback          (永久)                                   │
│   └── feedback_analysis (週報)                                   │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        反饋分析層                                │
│                                                                 │
│   定時排程（週/月）                                               │
│   ├── 差評對話根因分類                                            │
│   ├── 檢索品質分析（retrieved_chunks 比對）                       │
│   ├── Token 成本統計                                             │
│   └── 趨勢報表                                                   │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        迭代改善層                                │
│                                                                 │
│   Prompt 調整 → 知識庫補充 → Chunk 策略調整 → Reranker 參數      │
│                                                                 │
│   每次改善後重跑 Test Set 驗證效果                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 資料模型設計

### 2.1 現有表（已實作）— 需擴充欄位

```sql
-- conversations 表（現有，不需改動）
conversations (
    id          VARCHAR(36) PRIMARY KEY,
    tenant_id   VARCHAR(36) NOT NULL,
    bot_id      VARCHAR(36),
    created_at  TIMESTAMP WITH TIME ZONE
)

-- messages 表（現有，需擴充）
messages (
    id                VARCHAR(36) PRIMARY KEY,
    conversation_id   VARCHAR(36) NOT NULL,
    role              VARCHAR(20) NOT NULL,        -- user / assistant / tool
    content           TEXT NOT NULL,
    tool_calls_json   TEXT DEFAULT '[]',
    created_at        TIMESTAMP WITH TIME ZONE,

    -- ▼▼▼ 以下為新增欄位 ▼▼▼
    token_count_input   INT,                       -- LLM input token 數
    token_count_output  INT,                       -- LLM output token 數
    model               VARCHAR(50),               -- 使用的模型名稱
    latency_ms          INT,                       -- 回應耗時（毫秒）
    retrieved_chunks    JSONB,                      -- RAG 檢索到的 chunks
    -- 格式: [{"chunk_id": "...", "score": 0.92, "content": "...", "source": "..."}]
)
```

### 2.2 新增表 — 反饋

```sql
-- 使用者反饋（每則 assistant message 可收到一筆反饋）
feedback (
    id              VARCHAR(36) PRIMARY KEY,
    tenant_id       VARCHAR(36) NOT NULL,          -- 租戶隔離
    conversation_id VARCHAR(36) NOT NULL,
    message_id      VARCHAR(36) NOT NULL,           -- 對應哪則 assistant 回答
    user_id         VARCHAR(100),                   -- LINE user ID / Web user ID
    channel         VARCHAR(20) NOT NULL,           -- web / line / api
    rating          VARCHAR(20) NOT NULL,           -- thumbs_up / thumbs_down / 1-5
    comment         TEXT,                           -- 使用者追加的文字說明
    tags            JSONB DEFAULT '[]',             -- 問題分類標籤（可後續人工或 AI 標註）
    -- 格式: ["幻覺", "過時資訊", "語氣不當"]
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT fk_feedback_conversation
        FOREIGN KEY (conversation_id) REFERENCES conversations(id),

    CONSTRAINT uq_feedback_message
        UNIQUE (message_id)                         -- 每則訊息只接受一次反饋
)

CREATE INDEX ix_feedback_tenant ON feedback(tenant_id);
CREATE INDEX ix_feedback_rating ON feedback(tenant_id, rating);
CREATE INDEX ix_feedback_created ON feedback(tenant_id, created_at);
```

### 2.3 新增表 — 反饋分析報告（選用）

```sql
-- 週期性分析結果快照（供後台報表使用，避免每次即時查詢）
feedback_analysis (
    id              VARCHAR(36) PRIMARY KEY,
    tenant_id       VARCHAR(36) NOT NULL,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    total_conversations INT,
    total_messages      INT,
    total_feedback      INT,
    thumbs_up_count     INT,
    thumbs_down_count   INT,
    satisfaction_rate   DECIMAL(5,2),               -- thumbs_up / total_feedback * 100
    avg_latency_ms      INT,
    total_input_tokens  BIGINT,
    total_output_tokens BIGINT,
    estimated_llm_cost  DECIMAL(10,2),              -- 依公開定價估算
    top_issues          JSONB,                      -- 最常出現的問題類型
    -- 格式: [{"tag": "幻覺", "count": 23}, {"tag": "過時資訊", "count": 15}]
    created_at      TIMESTAMP WITH TIME ZONE
)
```

---

## 3. 反饋收集策略

### 3.1 Web Chat UI

| 時機 | 方式 | UX |
|------|------|-----|
| 每則回答 | 👍 👎 按鈕（不打擾） | 浮現在 assistant message 右下角 |
| 按 👎 後 | 追問原因（選項 + 自由文字） | Modal 或 inline 展開 |
| 對話結束 | 整體滿意度 1-5 星 | 對話結束 30 秒後彈出 |

```
👎 追問選項（預設，可依租戶自訂）：
├── 答案不正確
├── 答案不完整
├── 沒有回答我的問題
├── 語氣 / 格式不好
└── 其他（自由填寫）
```

### 3.2 LINE Bot

| 方式 | LINE 技術 | 觸發時機 |
|------|----------|---------|
| Quick Reply 👍👎 | `quickReply.items` | 每則回答自動附上 |
| 追問原因 | Postback Action | 使用者按 👎 後觸發 |
| 滿意度調查 | Flex Message | 偵測對話結束（N 分鐘無回應） |

#### LINE Postback Data 格式設計

```
# 按讚/倒讚
feedback:{message_id}:thumbs_up
feedback:{message_id}:thumbs_down

# 追問原因
feedback_reason:{message_id}:incorrect
feedback_reason:{message_id}:incomplete
feedback_reason:{message_id}:irrelevant
feedback_reason:{message_id}:tone

# 滿意度
satisfaction:{conversation_id}:{score}
```

#### LINE Quick Reply 範例

```json
{
  "type": "text",
  "text": "您的訂單 #12345 目前配送中，預計明天到達。",
  "quickReply": {
    "items": [
      {
        "type": "action",
        "action": {
          "type": "postback",
          "label": "👍 有幫助",
          "data": "feedback:msg-abc-123:thumbs_up",
          "displayText": "👍"
        }
      },
      {
        "type": "action",
        "action": {
          "type": "postback",
          "label": "👎 沒幫助",
          "data": "feedback:msg-abc-123:thumbs_down",
          "displayText": "👎"
        }
      }
    ]
  }
}
```

### 3.3 營運後台（人工標註）

- 客服主管可瀏覽差評對話，補充 `tags` 標籤
- 批次匯入外部標註結果（CSV）
- AI 輔助標註：用 LLM 自動分類差評原因，人工審核

---

## 4. DDD 層級設計

### 4.1 Domain 層

```
src/domain/conversation/
├── entity.py              # Conversation, Message（現有）
├── value_objects.py       # ConversationId, MessageId（現有）
├── repository.py          # ConversationRepository（現有）
├── feedback_entity.py     # ★ 新增：Feedback Entity
├── feedback_value_objects.py  # ★ 新增：Rating, Channel, FeedbackTag
└── feedback_repository.py     # ★ 新增：FeedbackRepository Interface
```

#### Feedback Entity

```python
@dataclass
class Feedback:
    id: FeedbackId
    tenant_id: str
    conversation_id: str
    message_id: str
    user_id: str | None
    channel: Channel              # web / line / api
    rating: Rating                # thumbs_up / thumbs_down / score_1..5
    comment: str | None
    tags: list[str]
    created_at: datetime
```

#### Value Objects

```python
class Rating(str, Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"

class Channel(str, Enum):
    WEB = "web"
    LINE = "line"
    API = "api"
```

### 4.2 Application 層

```
src/application/conversation/
├── send_message_use_case.py        # 現有
├── submit_feedback_use_case.py     # ★ 新增
└── analyze_feedback_use_case.py    # ★ 新增
```

### 4.3 Infrastructure 層

```
src/infrastructure/db/models/
├── conversation_model.py    # 現有
├── message_model.py         # 現有（擴充欄位）
└── feedback_model.py        # ★ 新增

src/infrastructure/db/repositories/
├── conversation_repository.py  # 現有
└── feedback_repository.py      # ★ 新增
```

### 4.4 Interfaces 層

```
src/interfaces/api/
├── conversation_router.py   # 現有（加 feedback endpoint）
└── webhook_router.py        # 現有（LINE postback 處理）
```

---

## 5. 反饋分析查詢（月報）

### 5.1 滿意度趨勢

```sql
SELECT
    DATE(f.created_at) AS date,
    COUNT(*) AS total_feedback,
    COUNT(*) FILTER (WHERE f.rating = 'thumbs_up') AS positive,
    COUNT(*) FILTER (WHERE f.rating = 'thumbs_down') AS negative,
    ROUND(
        COUNT(*) FILTER (WHERE f.rating = 'thumbs_up') * 100.0 / NULLIF(COUNT(*), 0),
        1
    ) AS satisfaction_pct
FROM feedback f
WHERE f.tenant_id = :tenant_id
  AND f.created_at >= NOW() - INTERVAL '1 month'
GROUP BY DATE(f.created_at)
ORDER BY date;
```

### 5.2 差評根因分析

```sql
SELECT
    tag,
    COUNT(*) AS count
FROM feedback f,
     LATERAL jsonb_array_elements_text(f.tags) AS tag
WHERE f.tenant_id = :tenant_id
  AND f.rating = 'thumbs_down'
  AND f.created_at >= NOW() - INTERVAL '1 month'
GROUP BY tag
ORDER BY count DESC;
```

### 5.3 檢索品質分析（哪些問題撈不到好的 chunk）

```sql
SELECT
    m_user.content AS user_question,
    m_asst.retrieved_chunks,
    f.rating,
    f.comment
FROM feedback f
JOIN messages m_asst ON m_asst.id = f.message_id
JOIN messages m_user ON m_user.conversation_id = m_asst.conversation_id
                    AND m_user.role = 'user'
                    AND m_user.created_at < m_asst.created_at
WHERE f.tenant_id = :tenant_id
  AND f.rating = 'thumbs_down'
  AND f.created_at >= NOW() - INTERVAL '1 month'
ORDER BY f.created_at DESC;
```

### 5.4 Token 成本統計

```sql
SELECT
    m.model,
    COUNT(*) AS message_count,
    SUM(m.token_count_input) AS total_input_tokens,
    SUM(m.token_count_output) AS total_output_tokens,
    AVG(m.latency_ms) AS avg_latency_ms,
    -- 以 GPT-4o 公開定價估算（可依實際模型調整）
    ROUND(SUM(m.token_count_input) / 1000000.0 * 2.5, 2) AS est_input_cost_usd,
    ROUND(SUM(m.token_count_output) / 1000000.0 * 10, 2) AS est_output_cost_usd
FROM messages m
JOIN conversations c ON c.id = m.conversation_id
WHERE c.tenant_id = :tenant_id
  AND m.role = 'assistant'
  AND m.created_at >= NOW() - INTERVAL '1 month'
GROUP BY m.model;
```

---

## 6. 反饋驅動的改善閉環

```
         收集                 分析                  改善               驗證
    ┌──────────┐        ┌──────────┐        ┌──────────┐        ┌──────────┐
    │ 👍👎     │        │ 週報     │        │ 調整     │        │ Test Set │
    │ Quick    │───────→│ 根因分類 │───────→│ Prompt   │───────→│ 回歸測試 │──┐
    │ Reply    │        │ 檢索分析 │        │ 知識庫   │        │ A/B 比較 │  │
    │ 人工標註 │        │ 成本統計 │        │ Chunk    │        │          │  │
    └──────────┘        └──────────┘        └──────────┘        └──────────┘  │
         ↑                                                                     │
         └─────────────────────────────────────────────────────────────────────┘
```

### 改善優先級判斷矩陣

| 分析結果 | 問題根因 | 調整什麼 | 優先級 |
|----------|---------|---------|--------|
| 差評中 40% 標記「答案不正確」 | retrieved_chunks 有正確資料但模型回答錯 | Prompt 工程 | P0 |
| 差評中 30% 標記「沒回答我的問題」 | retrieved_chunks 為空或不相關 | 知識庫內容 + Chunk 策略 | P0 |
| 差評中 20% 標記「答案不完整」 | Top-K 太小，只撈到部分資料 | 加大 K + Reranker | P1 |
| 差評中 10% 標記「語氣不好」 | System Prompt 語氣設定 | Prompt 工程 | P2 |
| latency P95 > 5s | 模型太大或 retrieved chunks 太多 | 換小模型 / 降 K | P1 |
| 月 LLM 成本超標 | token 用量高 | 換小模型 / 精簡 prompt | P1 |

---

## 7. 企業級考量

### 7.1 多租戶隔離

- 所有查詢都帶 `tenant_id`，A 租戶看不到 B 的反饋資料
- 反饋分析報表按租戶獨立產出
- 每個租戶可自訂 👎 追問選項（tags 清單）

### 7.2 資料保留與合規

| 資料類型 | 保留期限 | 說明 |
|----------|---------|------|
| 對話內容 | 依合約 / 法規（建議 6-12 個月） | 過期後匿名化或刪除 |
| 反饋資料 | 同對話 | 跟隨對話生命週期 |
| 分析報告 | 永久 | 只含統計數字，無個資 |
| Token 用量 | 永久 | 成本分析用 |

### 7.3 隱私保護

- 反饋資料中的個資（LINE user ID、對話內容）需加密或脫敏
- 匯出分析報告時自動遮蔽 PII
- GDPR / 個資法：使用者有權要求刪除其對話與反饋記錄

### 7.4 效能考量

- 反饋寫入走**異步**（不阻塞主對話流程）
- 月報查詢走**預計算快照**（`feedback_analysis` 表），不即時 scan 全表
- `retrieved_chunks` JSONB 欄位加 GIN 索引，支援快速查詢

### 7.5 營運後台功能需求

| 功能 | 說明 |
|------|------|
| 反饋儀表板 | 滿意度趨勢圖、差評比例、Top 問題 |
| 差評瀏覽器 | 逐筆查看差評對話，可人工標註 tags |
| 對話回放 | 完整重現一段對話（含 retrieved chunks） |
| A/B 測試管理 | Prompt 版本切換、流量分配、效果比較 |
| 匯出 | CSV / JSON 匯出指定期間的分析資料 |
