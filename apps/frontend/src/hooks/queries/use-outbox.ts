import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  BulkRequeueRequest,
  BulkRequeueResponse,
  ListDeadLetterParams,
  OutboxEvent,
  OutboxStats,
} from "@/types/outbox";

const STATS_REFETCH_INTERVAL_MS = 30_000;

export function useOutboxStats() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.outboxAdmin.stats,
    queryFn: () =>
      apiFetch<OutboxStats>(
        API_ENDPOINTS.adminOutbox.stats,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    refetchInterval: STATS_REFETCH_INTERVAL_MS,
  });
}

export function useOutboxDeadLetter(params: ListDeadLetterParams = {}) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.outboxAdmin.deadLetter(
      params.event_type,
      params.tenant_id,
    ),
    queryFn: () =>
      apiFetch<OutboxEvent[]>(
        API_ENDPOINTS.adminOutbox.deadLetter(params),
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useRetryOutboxEvent() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (eventId: string) =>
      apiFetch<OutboxEvent>(
        API_ENDPOINTS.adminOutbox.retry(eventId),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("事件已重排（status → pending）");
      qc.invalidateQueries({ queryKey: ["outbox"] });
    },
    onError: () => toast.error("重排失敗"),
  });
}

export function useBulkRetryOutbox() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BulkRequeueRequest) =>
      apiFetch<BulkRequeueResponse>(
        API_ENDPOINTS.adminOutbox.bulkRetry,
        { method: "POST", body: JSON.stringify(body) },
        token ?? undefined,
      ),
    onSuccess: (data) => {
      toast.success(`已批次重排 ${data.requeued_count} 筆事件`);
      qc.invalidateQueries({ queryKey: ["outbox"] });
    },
    onError: () => toast.error("批次重排失敗"),
  });
}

export function useAbandonOutboxEvent() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, reason }: { eventId: string; reason?: string }) =>
      apiFetch<void>(
        API_ENDPOINTS.adminOutbox.abandon(eventId),
        {
          method: "DELETE",
          body: JSON.stringify({ reason: reason ?? "" }),
        },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("事件已放棄（hard delete）");
      qc.invalidateQueries({ queryKey: ["outbox"] });
    },
    onError: () => toast.error("放棄失敗"),
  });
}
