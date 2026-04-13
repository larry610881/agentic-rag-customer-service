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

export const REQUEST_TYPE_LABELS: Record<string, string> = {
  chat_web: "Web 後台對話",
  chat_widget: "Widget 對話",
  chat_line: "LINE 對話",
  rag: "RAG 查詢",
  ocr: "PDF OCR",
  embedding: "Embedding 向量化",
  agent: "Web 後台對話",
};

export function getRequestTypeLabel(type: string): string {
  return REQUEST_TYPE_LABELS[type] ?? type;
}

export function isChatType(type: string): boolean {
  return type.startsWith("chat_") || type === "agent";
}

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
