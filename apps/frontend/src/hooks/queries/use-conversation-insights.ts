import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";

export interface ConversationMessageItem {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: unknown[];
  latency_ms?: number | null;
  retrieved_chunks?: unknown[] | null;
  structured_content?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface ConversationMessagesResponse {
  conversation_id: string;
  tenant_id: string;
  bot_id?: string | null;
  created_at?: string | null;
  summary?: string | null;
  message_count: number;
  last_message_at?: string | null;
  messages: ConversationMessageItem[];
}

export interface ConversationTokenUsageRow {
  model: string;
  request_type: string;
  kb_id?: string | null;
  kb_name?: string | null;
  bot_id?: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  estimated_cost: number;
  message_count: number;
}

export interface ConversationTokenUsageTotals {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  estimated_cost: number;
  message_count: number;
}

export interface ConversationTokenUsageResponse {
  conversation_id: string;
  totals: ConversationTokenUsageTotals;
  by_request_type: ConversationTokenUsageRow[];
}

export function useConversationMessages(conversationId: string | null) {
  return useQuery({
    queryKey: queryKeys.admin.conversationMessages(conversationId ?? ""),
    queryFn: () =>
      apiFetch<ConversationMessagesResponse>(
        API_ENDPOINTS.adminConversations.messages(conversationId!),
      ),
    enabled: !!conversationId,
    staleTime: 30_000,
  });
}

export function useConversationTokenUsage(conversationId: string | null) {
  return useQuery({
    queryKey: queryKeys.admin.conversationTokenUsage(conversationId ?? ""),
    queryFn: () =>
      apiFetch<ConversationTokenUsageResponse>(
        API_ENDPOINTS.adminConversations.tokenUsage(conversationId!),
      ),
    enabled: !!conversationId,
    staleTime: 30_000,
  });
}
