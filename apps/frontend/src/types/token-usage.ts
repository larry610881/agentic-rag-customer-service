export interface TenantBotUsageStat {
  tenant_id: string;
  tenant_name: string;
  bot_id: string | null;
  bot_name: string | null;
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
