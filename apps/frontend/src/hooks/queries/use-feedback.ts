import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import { useChatStore } from "@/stores/use-chat-store";
import type {
  DailyFeedbackStat,
  FeedbackResponse,
  FeedbackStats,
  ModelCostStat,
  RetrievalQualityRecord,
  SubmitFeedbackRequest,
  TagCount,
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

export function useFeedbackList(limit = 50, offset = 0) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.feedback.list(tenantId ?? ""),
    queryFn: () =>
      apiFetch<FeedbackResponse[]>(
        `${API_ENDPOINTS.feedback.list}?limit=${limit}&offset=${offset}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useSatisfactionTrend(days = 30) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.feedback.trend(tenantId ?? "", days),
    queryFn: () =>
      apiFetch<DailyFeedbackStat[]>(
        `${API_ENDPOINTS.feedback.satisfactionTrend}?days=${days}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useTopIssues(days = 30, limit = 10) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.feedback.topIssues(tenantId ?? "", days),
    queryFn: () =>
      apiFetch<TagCount[]>(
        `${API_ENDPOINTS.feedback.topIssues}?days=${days}&limit=${limit}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useRetrievalQuality(days = 30, limit = 20) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.feedback.retrievalQuality(tenantId ?? "", days),
    queryFn: () =>
      apiFetch<RetrievalQualityRecord[]>(
        `${API_ENDPOINTS.feedback.retrievalQuality}?days=${days}&limit=${limit}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useTokenCostStats(days = 30) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.feedback.tokenCost(tenantId ?? "", days),
    queryFn: () =>
      apiFetch<ModelCostStat[]>(
        `${API_ENDPOINTS.feedback.tokenCost}?days=${days}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useFeedbackByConversation(conversationId: string | null) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.feedback.byConversation(conversationId ?? ""),
    queryFn: () =>
      apiFetch<FeedbackResponse[]>(
        API_ENDPOINTS.feedback.byConversation(conversationId!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!conversationId,
  });
}

export function useUpdateFeedbackTags() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ feedbackId, tags }: { feedbackId: string; tags: string[] }) =>
      apiFetch<{ status: string }>(
        API_ENDPOINTS.feedback.updateTags(feedbackId),
        {
          method: "PATCH",
          body: JSON.stringify({ tags }),
        },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.feedback.list(tenantId ?? ""),
      });
    },
  });
}
