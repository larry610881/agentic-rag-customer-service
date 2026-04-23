export interface TenantBotUsageStat {
  tenant_id: string;
  tenant_name: string;
  bot_id: string | null;
  bot_name: string | null;
  kb_id?: string | null;
  kb_name?: string | null;
  model: string;
  request_type: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  message_count: number;
}

export type UsageSourceKind = "bot" | "kb" | "system";

/**
 * 以 request_type + bot_id/kb_id 推論本筆記錄的「來源類型」。
 * 用於表格合併「機器人/知識庫」欄、以及頂部來源類型 filter。
 */
const KB_REQUEST_TYPES = new Set([
  "ocr",
  "contextual_retrieval",
  "auto_classification",
  "pdf_rename",
  "embedding",
]);

export interface UsageSourceInfo {
  kind: UsageSourceKind;
  icon: string;
  name: string;
  href?: string;
}

export function inferUsageSource(row: TenantBotUsageStat): UsageSourceInfo {
  // 1. 有 bot_id → 機器人來源（chat_web/widget/line、intent_classify、conversation_summary 等）
  if (row.bot_id) {
    return {
      kind: "bot",
      icon: "🤖",
      name: row.bot_name ?? "未命名機器人",
      href: `/bots/${row.bot_id}`,
    };
  }
  // 2. 已知 KB 類型 → 知識庫來源
  if (KB_REQUEST_TYPES.has(row.request_type)) {
    return {
      kind: "kb",
      icon: "📚",
      name: row.kb_name ?? "知識庫處理",
      href: row.kb_id ? `/knowledge/${row.kb_id}` : undefined,
    };
  }
  // 3. 其他 → 系統
  return { kind: "system", icon: "⚙️", name: "系統" };
}

export interface BotUsageStat {
  bot_id: string | null;
  bot_name: string | null;
  model: string;
  request_type: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  message_count: number;
}

// Token-Gov.6: category label 的 single source of truth 移至 constants/usage-categories.ts
// 本檔 re-export 保持 backward compat（既有 import 不需改）
export {
  USAGE_CATEGORIES,
  getCategoryLabel as getRequestTypeLabel,
  getCategoryShortLabel,
  isChatType,
} from "@/constants/usage-categories";

import { USAGE_CATEGORIES } from "@/constants/usage-categories";

/**
 * @deprecated 改用 getCategoryLabel / getCategoryShortLabel。
 * 保留本對照表以兼容既有直接 lookup 的程式碼。Stage 5 會逐一替換後刪除。
 */
export const REQUEST_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  USAGE_CATEGORIES.map((c) => [c.value, c.label]),
);

export interface DailyUsageStat {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  message_count: number;
}

export interface MonthlyUsageStat {
  month: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  message_count: number;
}
