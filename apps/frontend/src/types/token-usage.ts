export interface TenantBotUsageStat {
  tenant_id: string;
  tenant_name: string;
  bot_id: string | null;
  bot_name: string | null;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  message_count: number;
}
