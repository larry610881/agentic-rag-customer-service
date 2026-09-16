# ADR-0003: 對話管線統一（ConversationTurnPipeline）— 現況盤點與分階段決策

**Status**: Proposed（分階段執行中；本 ADR 記錄 2026-09-16 的盤點與下一步）
**Date**: 2026-09-16
**Deciders**: Larry (product owner), Claude (architecture)
**Context**: `.claude/rules/channel-parity.md` 的絞殺者遷移清單第 8 項「最終：`ConversationTurnPipeline` 共用管線 + 中性事件流輸出」。前七項在 2026-09 陸續還清，本文評估第 8 項是否、何時、怎麼做。

---

## 1. 現況（2026-09-16）

兩條 use case 仍各自存在：`application/agent/send_message_use_case.py`（web / widget）與
`application/line/handle_webhook_use_case.py`（LINE）。但「管線步驟」已陸續抽成共用 service，
兩邊只剩呼叫：

| 管線步驟 | 共用實作 | web | LINE | 備註 |
|---|---|---|---|---|
| 快速道 / kb 模式檢索決策 | `DirectRetrievalService` | ✅ | ✅ | #61 |
| 輸入防護、分類器攻擊、kb 攻擊判定 | `GuardPipeline` | ✅ | ✅ | #75；LINE 與意圖分類並行執行（延遲優化），結果語意相同 |
| 攔截回應組裝（守 bot 輸出格式） | `guard_responses.blocked_input_response` | ✅ | ✅ | #99 二-3；LINE 補上 `structured_output` |
| 輸出格式 / 未命中 / 攔截的 finalize | `output_format.*` | ✅ | ✅ | #70 / #85 |
| 有效設定指紋 | `ConfigFingerprintService` | ✅ | ✅ | #60 |
| trace 持久化（含 outcome） | `trace_persistence.persist_finished_trace` | ✅ | ✅ | #99 二-2；M20 根治 |
| 記帳 | `RecordUsageUseCase`（use case 內呼叫） | ✅ | ✅ | #96；串流收尾 shielded |
| 長期記憶載入 / 萃取 | `ConversationMemoryService` | ✅ | ✅ | #99 二-6；LINE 首次接上 |
| 異常控管計分 / 保守模式 | `AbuseControlService` | ✅ | ✅ | #68 |
| 冪等 / 快照重播 | `IdempotencyGuard` | ✅ | webhookEventId 去重 | #95 / #99；LINE 由平台 event id 提供等價語意 |
| 線上 eval | — | 已下線 | 已下線 | #59；債務第 4 項劃掉 |

**仍是兩份的**：
1. **回合編排本體**：載入對話 → bot 設定 → history → 記憶 → worker 路由 → 快速道 → 生成 → 收尾 → 尾端。
   兩邊順序與條件相同，但各寫一遍（web 約 1,900 行、LINE 約 1,400 行）。
2. **LINE 的 prompt / worker 設定組裝**（`_resolve_worker_config` 的 LINE 版）與 web 的 `_load_bot_config` 是平行實作。
3. **輸出**：web 是事件流（SSE）與 `AgentResponse`；LINE 是聚合後的 flex / 文字回覆。

## 2. 決策

**不做大爆炸重寫。** 以「中性事件流」為介面，分三階段把編排本體收斂成一份：

### Phase A（可立即做，1–2 天）— 設定組裝合一
- 把 web 的 `_load_bot_config` + `_resolve_worker_config` 與 LINE 的對應段落抽成
  `TurnConfigResolver.resolve(bot, message, channel_caps) -> TurnConfig`（含 prompt、kb、工具、
  worker、快速道 plan、config_hash）。
- LINE 的並行 guard + 分類保留為 resolver 的實作細節（能力旗標 `guard_parallel=True`）。
- 驗收：兩通路對同一 bot / 同一問句產生相同的 `config_hash`。

### Phase B（2–3 天）— 回合編排合一
- `ConversationTurnPipeline.run(command, caps) -> AsyncIterator[TurnEvent]`：一份編排，
  輸出中性事件（token / sources / structured_output / guard_blocked / message_id / done …，
  即今天 SSE 事件的型別清單）。
- web 串流：事件直接編成 SSE；web 非串流：聚合成 `AgentResponse`；LINE：聚合成回覆＋flex。
  三個都是 interfaces 層的轉接器。
- `SendMessageUseCase.execute / execute_stream` 與 `HandleWebhookUseCase.process_and_push`
  變成薄包裝，舊測試不動。

### Phase C（0.5 天）— 閘門 replay 通路保真
- replay 以 `caps` 指定來源通路（LINE：非串流、純文字、無來源卡）跑同一條管線；
  `pipeline_approximation` 標記移除。#99 二-7 先以「bot 是否綁 LINE」給出保真度標注，屬過渡。

## 3. 不做的事

- 不把 LINE 的 flex 圖卡 / 回覆推送搬進管線（那是 I/O 轉接，規範明定留在通路目錄）。
- 不為統一而改變任何一通路的現行行為；每個 phase 的驗收都是「家樂福 LINE 行為零回歸」。

## 4. 觸發條件

Phase A 在下一次任何需要「同時改兩條 use case 的管線邏輯」的需求出現時啟動——那正是
規範說的「順手還債優先於再堆一層」。若三個月內沒有這類需求，維持現狀（共用 service 已足以
防止 drift）。
