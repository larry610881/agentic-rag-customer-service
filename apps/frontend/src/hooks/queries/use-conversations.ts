import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  ConversationSummary,
  ConversationDetail,
} from "@/types/conversation";

export function useConversations() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.conversations.all(tenantId ?? ""),
    queryFn: () =>
      apiFetch<ConversationSummary[]>(
        API_ENDPOINTS.conversations.list,
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
