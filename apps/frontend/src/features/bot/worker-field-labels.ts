/**
 * Issue #77 — Worker（bot 底下的分流子機器人）欄位中文名對照表 + 值格式器。
 * 與 bot 相同語意的欄位（temperature / max_tokens / knowledge_base_ids …）沿用
 * bot-field-labels 的格式器，兩種實體在變更紀錄中的顯示方式一致。
 */

import {
  describeLengthChange,
  formatBotFieldValue,
} from "@/features/bot/bot-field-labels";
import { isLongTextChange, type BotAuditChange } from "@/types/bot-audit-log";

export const WORKER_FIELD_LABELS: Record<string, string> = {
  name: "名稱",
  description: "路由描述",
  worker_prompt: "專屬提示詞",
  llm_provider: "模型供應商",
  llm_model: "模型",
  temperature: "溫度",
  max_tokens: "最大 Token 數",
  max_tool_calls: "最大迭代次數",
  direct_retrieval: "快速道（直接檢索）",
  knowledge_base_ids: "知識庫",
  enabled_tools: "啟用工具",
  enabled_mcp_ids: "MCP 工具",
  tool_configs: "工具檢索覆寫",
  sort_order: "排序",
};

/** 提示詞類長文字：紀錄只顯示字數增減，不顯示全文 */
export const WORKER_LONG_TEXT_FIELDS = new Set(["worker_prompt"]);

function leafKey(key: string): string {
  return key.includes(".") ? key.slice(key.lastIndexOf(".") + 1) : key;
}

/** 未知鍵回原鍵（與 botFieldLabel 同策略；支援 `llm_params.temperature` 形式） */
export function workerFieldLabel(key: string): string {
  return WORKER_FIELD_LABELS[key] ?? WORKER_FIELD_LABELS[leafKey(key)] ?? key;
}

/**
 * Worker 欄位值 → 可讀字串。
 * `enabled_tools` 為 null 表示「繼承 Bot」（[] 才是「無工具」），其餘與 bot 相同。
 */
export function formatWorkerFieldValue(key: string, value: unknown): string {
  const leaf = leafKey(key);
  if (leaf === "enabled_tools" && (value === null || value === undefined)) {
    return "繼承 Bot";
  }
  if (leaf === "llm_model" && (value === null || value === undefined || value === "")) {
    return "Bot 預設";
  }
  return formatBotFieldValue(key, value);
}

/** 單一 worker 變更 → 「專屬提示詞：已修改（+120 字）」 / 「溫度：0.3 → 0.7」 */
export function describeWorkerChange(change: BotAuditChange): string {
  const label = workerFieldLabel(change.field);
  if (isLongTextChange(change)) {
    return `${label}：${describeLengthChange(change.before_len, change.after_len)}`;
  }
  return `${label}：${formatWorkerFieldValue(change.field, change.before)} → ${formatWorkerFieldValue(change.field, change.after)}`;
}
