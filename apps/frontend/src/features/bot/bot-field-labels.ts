/**
 * Issue #71 — Bot 欄位中文名對照表 + 值格式器（與 abuse-setting-labels 同型式）。
 * 供「儲存前變更簡述」與「變更紀錄」共用，兩處顯示的欄位名與值一致。
 */

import { isLongTextChange, type BotAuditChange } from "@/types/bot-audit-log";
import { guardStageLabel } from "@/features/guard-stages/guard-stage-labels";

/** 前端儲存前 diff 的單一欄位（值取自表單基準與送出 payload） */
export interface BotFieldDiff {
  field: string;
  before: unknown;
  after: unknown;
}

export const BOT_FIELD_LABELS: Record<string, string> = {
  // 基本
  name: "名稱",
  description: "描述",
  is_active: "狀態",
  // 提示詞
  bot_prompt: "Bot 自訂指令",
  memory_extraction_prompt: "記憶萃取提示詞",
  // LLM
  llm_provider: "模型供應商",
  llm_model: "模型",
  temperature: "溫度",
  max_tokens: "最大 Token 數",
  history_limit: "歷史訊息數",
  frequency_penalty: "頻率懲罰",
  reasoning_effort: "推理強度",
  mode: "推理模式",
  max_tool_calls: "工具呼叫上限",
  // 輸出
  output_format: "輸出格式",
  output_schema: "JSON schema",
  miss_reply: "未命中話術",
  output_text_field: "通路顯示欄位",
  // 能力 / 檢索
  enabled_tools: "啟用工具",
  knowledge_base_ids: "知識庫",
  rag_top_k: "Top K",
  rag_score_threshold: "分數閾值",
  rag_retrieval_modes: "檢索模式",
  rerank_enabled: "Rerank",
  rerank_model: "Rerank 模型",
  rerank_top_n: "Rerank Top N",
  query_rewrite_enabled: "查詢改寫",
  query_rewrite_model: "Rewrite 模型",
  query_rewrite_extra_hint: "查詢改寫額外提示詞",
  hyde_enabled: "HyDE",
  hyde_model: "HyDE 模型",
  hyde_extra_hint: "HyDE 額外提示詞",
  tool_configs: "工具檢索覆寫",
  mcp_servers: "MCP 伺服器",
  mcp_bindings: "MCP 綁定",
  intent_routes: "意圖路由",
  router_model: "意圖分類模型",
  summary_model: "對話摘要模型",
  show_sources: "顯示來源",
  // 記憶
  memory_enabled: "長期記憶",
  // 防護
  guard_stages: "防護階段",
  memory_extraction_threshold: "記憶萃取門檻",
  // 評估
  eval_provider: "評估供應商",
  eval_model: "評估用模型",
  eval_depth: "評估深度",
  // 發布閘門
  gate_mode: "發布閘門",
  gate_soft_threshold: "閘門軟門檻",
  gate_repeats: "閘門重複次數",
  gate_auto_publish: "閘門自動發布",
  gate_daily_limit: "閘門每日上限",
  gate_budget_usd: "閘門預算（USD）",
  gate_excluded_cases: "閘門排除案例",
  // Widget
  widget_enabled: "Widget 啟用",
  widget_allowed_origins: "Widget 允許來源",
  widget_keep_history: "Widget 保留歷史",
  widget_welcome_message: "Widget 歡迎訊息",
  widget_placeholder_text: "Widget 輸入提示",
  widget_greeting_messages: "Widget 問候語",
  widget_greeting_animation: "Widget 問候動畫",
  customer_service_url: "真人客服網址",
  // LINE
  line_channel_secret: "LINE 頻道密鑰",
  line_channel_access_token: "LINE 存取權杖",
  line_show_sources: "LINE 顯示來源",
  busy_reply_message: "忙碌中回覆訊息",
};

/** 提示詞類長文字：簡述 / 紀錄只顯示字數增減，不顯示全文 */
export const LONG_TEXT_FIELDS = new Set([
  "bot_prompt",
  "memory_extraction_prompt",
  "query_rewrite_extra_hint",
  "hyde_extra_hint",
]);

/** 憑證：任何情境都不顯示值 */
export const SECRET_FIELDS = new Set([
  "line_channel_secret",
  "line_channel_access_token",
]);

export const BOT_MODE_LABELS: Record<string, string> = {
  fast: "快速",
  deep: "深度",
  kb: "知識庫問答",
};

export const BOT_OUTPUT_FORMAT_LABELS: Record<string, string> = {
  text: "一般",
  plain_text: "純文字",
  json: "JSON",
};

export const REASONING_EFFORT_LABELS: Record<string, string> = {
  none: "關閉",
  low: "低",
  medium: "中",
  high: "高",
};

export const GATE_MODE_LABELS: Record<string, string> = {
  off: "關閉",
  warn: "警告",
  block: "阻擋",
};

export const GREETING_ANIMATION_LABELS: Record<string, string> = {
  fade: "淡入",
  slide: "滑入",
  typewriter: "打字機",
};

const ENUM_LABELS: Record<string, Record<string, string>> = {
  mode: BOT_MODE_LABELS,
  output_format: BOT_OUTPUT_FORMAT_LABELS,
  reasoning_effort: REASONING_EFFORT_LABELS,
  gate_mode: GATE_MODE_LABELS,
  widget_greeting_animation: GREETING_ANIMATION_LABELS,
};

const EMPTY = "（空）";
const SECRET_MASK = "••••••";

/** `llm_params.temperature` → 「溫度」；未知鍵回原鍵 */
export function botFieldLabel(key: string): string {
  const direct = BOT_FIELD_LABELS[key];
  if (direct) return direct;
  const leaf = key.includes(".") ? key.slice(key.lastIndexOf(".") + 1) : key;
  return BOT_FIELD_LABELS[leaf] ?? key;
}

function leafKey(key: string): string {
  return key.includes(".") ? key.slice(key.lastIndexOf(".") + 1) : key;
}

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value as object).length === 0;
  return false;
}

/** 依欄位把值轉成可讀字串（簡述 / 紀錄共用） */
export function formatBotFieldValue(key: string, value: unknown): string {
  const leaf = leafKey(key);
  if (SECRET_FIELDS.has(leaf)) return isEmptyValue(value) ? EMPTY : SECRET_MASK;
  if (isEmptyValue(value)) return EMPTY;
  if (leaf === "is_active" && typeof value === "boolean") {
    return value ? "啟用" : "停用";
  }
  if (typeof value === "boolean") return value ? "開" : "關";
  if (leaf === "guard_stages" && Array.isArray(value)) {
    return value.map((v) => guardStageLabel(String(v))).join("、");
  }
  const enumMap = ENUM_LABELS[leaf];
  if (enumMap && typeof value === "string") return enumMap[value] ?? value;
  if (Array.isArray(value)) {
    return value
      .map((v) => (typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)))
      .join("、");
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** 長文字：以字數增減描述（+120 字 / −30 字 / 字數不變） */
export function describeLengthChange(beforeLen: number, afterLen: number): string {
  const delta = afterLen - beforeLen;
  if (delta === 0) return "已修改（字數不變）";
  return delta > 0 ? `已修改（+${delta} 字）` : `已修改（−${Math.abs(delta)} 字）`;
}

function textLength(value: unknown): number {
  return typeof value === "string" ? value.length : 0;
}

/** 單一變更 → 「模型：gpt-4o → gemini-3.7-flash」 / 「Bot 自訂指令：已修改（+120 字）」 */
export function describeBotChange(change: BotAuditChange | BotFieldDiff): string {
  const label = botFieldLabel(change.field);
  if (isLongTextChange(change as BotAuditChange)) {
    const c = change as { before_len: number; after_len: number };
    return `${label}：${describeLengthChange(c.before_len, c.after_len)}`;
  }
  const { before, after } = change as BotFieldDiff;
  if (LONG_TEXT_FIELDS.has(leafKey(change.field))) {
    return `${label}：${describeLengthChange(textLength(before), textLength(after))}`;
  }
  return `${label}：${formatBotFieldValue(change.field, before)} → ${formatBotFieldValue(change.field, after)}`;
}

/** 正規化後比較：空值（null / undefined / "" / [] / {}）視為同一種「空」，物件深比較 */
function normalize(value: unknown): string {
  if (isEmptyValue(value)) return "";
  if (typeof value === "object") return JSON.stringify(sortKeys(value));
  return JSON.stringify(value);
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value as Record<string, unknown>)
        .sort()
        .map((k) => [k, sortKeys((value as Record<string, unknown>)[k])]),
    );
  }
  return value;
}

/**
 * 儲存前 diff：只比對 `after`（送出 payload）含有的欄位，`before` 為表單基準值。
 * 結果依 BOT_FIELD_LABELS 的宣告順序排序，未知欄位排最後。
 */
export function diffBotValues(
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): BotFieldDiff[] {
  const order = Object.keys(BOT_FIELD_LABELS);
  const rank = (k: string) => {
    const i = order.indexOf(k);
    return i === -1 ? order.length : i;
  };
  return Object.keys(after)
    .filter((key) => normalize(before[key]) !== normalize(after[key]))
    .sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
    .map((field) => ({ field, before: before[field], after: after[field] }));
}
