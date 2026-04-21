import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface ConversationSearchResult {
  conversation_id: string;
  tenant_id: string;
  tenant_name: string;
  bot_id: string | null;
  summary: string;
  first_message_at: string | null;
  last_message_at: string | null;
  message_count: number;
  score: number | null;
  matched_via: "keyword" | "semantic";
}

interface UseConversationSearchParams {
  mode: "keyword" | "semantic";
  query: string;
  tenantId?: string;
  botId?: string;
  limit?: number;
  enabled?: boolean;
}

/**
 * S-Gov.6b: Hybrid 對話搜尋 — keyword (PG ILIKE) 或 semantic (Milvus vector)。
 *
 * mode=keyword 走 PG ILIKE on conversations.summary（精準字面）
 * mode=semantic 走 Milvus vector search on conv_summaries（語意相近）
 *
 * 兩模式互斥；UI 強制只能擇一傳入。
 */
export function useConversationSearch({
  mode,
  query,
  tenantId,
  botId,
  limit = 20,
  enabled = true,
}: UseConversationSearchParams) {
  const token = useAuthStore((s) => s.token);
  const trimmed = query.trim();

  return useQuery({
    queryKey: queryKeys.admin.conversationSearch(
      mode,
      trimmed,
      tenantId ?? "all",
      botId ?? "all",
    ),
    queryFn: () =>
      apiFetch<ConversationSearchResult[]>(
        API_ENDPOINTS.adminConversations.search({
          keyword: mode === "keyword" ? trimmed : undefined,
          semantic: mode === "semantic" ? trimmed : undefined,
          tenantId,
          botId,
          limit,
        }),
        {},
        token ?? undefined,
      ),
    enabled: !!token && enabled && trimmed.length > 0,
    staleTime: 60_000,
  });
}
