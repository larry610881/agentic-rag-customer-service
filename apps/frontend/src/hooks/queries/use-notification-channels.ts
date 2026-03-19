import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  NotificationChannel,
  CreateChannelPayload,
} from "@/types/error-event";

export function useNotificationChannels() {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  return useQuery({
    queryKey: queryKeys.notificationChannels.all,
    queryFn: async () => {
      const res = await apiFetch<{ items: NotificationChannel[] }>(
        API_ENDPOINTS.notificationChannels.list,
        {},
        token ?? undefined,
      );
      return res.items;
    },
    enabled: !!token && role === "system_admin",
  });
}

export function useCreateChannel() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateChannelPayload) =>
      apiFetch<NotificationChannel>(
        API_ENDPOINTS.notificationChannels.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.notificationChannels.all,
      });
    },
  });
}

export function useUpdateChannel() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<CreateChannelPayload>;
    }) =>
      apiFetch<NotificationChannel>(
        API_ENDPOINTS.notificationChannels.update(id),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.notificationChannels.all,
      });
    },
  });
}

export function useDeleteChannel() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(
        API_ENDPOINTS.notificationChannels.delete(id),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.notificationChannels.all,
      });
    },
  });
}

export function useTestChannel() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ success: boolean; message: string }>(
        API_ENDPOINTS.notificationChannels.test(id),
        { method: "POST" },
        token ?? undefined,
      ),
  });
}
