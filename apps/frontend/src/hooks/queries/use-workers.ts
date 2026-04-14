import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  WorkerConfig,
  CreateWorkerRequest,
  UpdateWorkerRequest,
} from "@/types/worker-config";

export function useWorkers(botId: string | undefined) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.bots.workers(botId ?? ""),
    queryFn: () =>
      apiFetch<WorkerConfig[]>(
        API_ENDPOINTS.bots.workers(botId!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId,
  });
}

export function useCreateWorker(botId: string) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateWorkerRequest) =>
      apiFetch<WorkerConfig>(
        API_ENDPOINTS.bots.workers(botId),
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bots.workers(botId),
      });
    },
  });
}

export function useUpdateWorker(botId: string) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      workerId,
      data,
    }: {
      workerId: string;
      data: UpdateWorkerRequest;
    }) =>
      apiFetch<WorkerConfig>(
        API_ENDPOINTS.bots.worker(botId, workerId),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bots.workers(botId),
      });
    },
  });
}

export function useDeleteWorker(botId: string) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (workerId: string) =>
      apiFetch<void>(
        API_ENDPOINTS.bots.worker(botId, workerId),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bots.workers(botId),
      });
    },
  });
}
