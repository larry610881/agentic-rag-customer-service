import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface LogRetentionPolicy {
  id: string;
  enabled: boolean;
  retention_days: number;
  cleanup_hour: number;
  cleanup_interval_hours: number;
  last_cleanup_at: string | null;
  deleted_count_last: number;
  updated_at: string;
}

interface UpdateLogRetentionBody {
  enabled: boolean;
  retention_days: number;
  cleanup_hour: number;
  cleanup_interval_hours: number;
}

interface CleanupResult {
  deleted_count: number;
}

export function useLogRetentionPolicy() {
  const token = useAuthStore((s) => s.token);
  return useQuery<LogRetentionPolicy>({
    queryKey: queryKeys.observability.logRetention,
    queryFn: () =>
      apiFetch<LogRetentionPolicy>(
        API_ENDPOINTS.observability.logRetention,
        {},
        token ?? undefined,
      ),
  });
}

export function useUpdateLogRetentionPolicy() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation<LogRetentionPolicy, Error, UpdateLogRetentionBody>({
    mutationFn: (body) =>
      apiFetch<LogRetentionPolicy>(
        API_ENDPOINTS.observability.logRetention,
        { method: "PUT", body: JSON.stringify(body) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.observability.logRetention,
      });
    },
  });
}

export function useExecuteLogCleanup() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  return useMutation<CleanupResult, Error, void>({
    mutationFn: () =>
      apiFetch<CleanupResult>(
        API_ENDPOINTS.observability.executeLogCleanup,
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.observability.logRetention,
      });
    },
  });
}
