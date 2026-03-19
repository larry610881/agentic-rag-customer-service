import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import type {
  ConversationSummary,
  ConversationDetail,
} from "@/types/conversation";
import type { PaginatedResponse } from "@/types/api";

export function useConversations(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const botId = useChatStore((s) => s.botId);

  const baseUrl = API_ENDPOINTS.conversations.list(botId);
  const separator = baseUrl.includes("?") ? "&" : "?";
  const url = `${baseUrl}${separator}page=${page}&page_size=${pageSize}`;

  return useQuery({
    queryKey: [...queryKeys.conversations.all(tenantId ?? "", botId), page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<ConversationSummary>>(
        url,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useConversation(conversationId: string | null) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.conversations.detail(conversationId ?? ""),
    queryFn: () =>
      apiFetch<ConversationDetail>(
        API_ENDPOINTS.conversations.detail(conversationId!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!conversationId,
  });
}
