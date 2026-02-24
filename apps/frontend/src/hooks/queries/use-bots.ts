import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { Bot, CreateBotRequest, UpdateBotRequest } from "@/types/bot";

export function useBots() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: queryKeys.bots.all(tenantId ?? ""),
    queryFn: () =>
      apiFetch<Bot[]>(API_ENDPOINTS.bots.list, {}, token ?? undefined),
    enabled: !!token && !!tenantId,
  });
}

export function useBot(botId: string) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.bots.detail(botId),
    queryFn: () =>
      apiFetch<Bot>(
        API_ENDPOINTS.bots.detail(botId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId,
  });
}

export function useCreateBot() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateBotRequest) =>
      apiFetch<Bot>(
        API_ENDPOINTS.bots.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bots.all(tenantId ?? ""),
      });
    },
  });
}

export function useUpdateBot() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ botId, data }: { botId: string; data: UpdateBotRequest }) =>
      apiFetch<Bot>(
        API_ENDPOINTS.bots.update(botId),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bots.all(tenantId ?? ""),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bots.detail(variables.botId),
      });
    },
  });
}

export function useDeleteBot() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (botId: string) =>
      apiFetch<void>(
        API_ENDPOINTS.bots.delete(botId),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bots.all(tenantId ?? ""),
      });
    },
  });
}
