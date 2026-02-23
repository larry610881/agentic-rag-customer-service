import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { TaskResponse } from "@/types/knowledge";

export function useTask(taskId: string | null) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.tasks.detail(taskId ?? ""),
    queryFn: () =>
      apiFetch<TaskResponse>(
        API_ENDPOINTS.tasks.detail(taskId!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!taskId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "completed" || data.status === "failed")) {
        return false;
      }
      return 2000;
    },
  });
}
