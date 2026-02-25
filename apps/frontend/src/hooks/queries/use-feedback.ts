import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import type {
  FeedbackResponse,
  FeedbackStats,
  SubmitFeedbackRequest,
} from "@/types/feedback";

export function useSubmitFeedback() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const setMessageFeedback = useChatStore((s) => s.setMessageFeedback);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SubmitFeedbackRequest) =>
      apiFetch<FeedbackResponse>(API_ENDPOINTS.feedback.submit, {
        method: "POST",
        body: JSON.stringify(data),
      }, token ?? undefined),
    onMutate: (variables) => {
      setMessageFeedback(variables.message_id, variables.rating);
    },
    onError: (_error, variables) => {
      setMessageFeedback(variables.message_id, undefined);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.feedback.stats(tenantId ?? ""),
      });
    },
  });
}

export function useFeedbackStats() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.feedback.stats(tenantId ?? ""),
    queryFn: () =>
      apiFetch<FeedbackStats>(
        API_ENDPOINTS.feedback.stats,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}
