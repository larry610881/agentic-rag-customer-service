import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  ConnectionResult,
  CreateProviderSettingRequest,
  EnabledModel,
  ProviderSetting,
  UpdateProviderSettingRequest,
} from "@/types/provider-setting";

export function useProviderSettings(type?: string) {
  const token = useAuthStore((s) => s.token);

  const url = type
    ? `${API_ENDPOINTS.providerSettings.list}?type=${type}`
    : API_ENDPOINTS.providerSettings.list;

  return useQuery({
    queryKey: type
      ? queryKeys.providerSettings.byType(type)
      : queryKeys.providerSettings.all,
    queryFn: () =>
      apiFetch<ProviderSetting[]>(url, {}, token ?? undefined),
    enabled: !!token,
  });
}

export function useCreateProviderSetting() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProviderSettingRequest) =>
      apiFetch<ProviderSetting>(
        API_ENDPOINTS.providerSettings.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.providerSettings.all,
      });
    },
  });
}

export function useUpdateProviderSetting() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: UpdateProviderSettingRequest;
    }) =>
      apiFetch<ProviderSetting>(
        API_ENDPOINTS.providerSettings.update(id),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.providerSettings.all,
      });
    },
  });
}

export function useDeleteProviderSetting() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(
        API_ENDPOINTS.providerSettings.delete(id),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.providerSettings.all,
      });
    },
  });
}

export function useTestProviderConnection() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<ConnectionResult>(
        API_ENDPOINTS.providerSettings.testConnection(id),
        { method: "POST" },
        token ?? undefined,
      ),
  });
}

export function useEnabledModels() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.providerSettings.enabledModels,
    queryFn: () =>
      apiFetch<EnabledModel[]>(
        API_ENDPOINTS.providerSettings.enabledModels,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export type ModelRegistryEntry = {
  model_id: string;
  display_name: string;
  price: string;
};

export type ModelRegistry = Record<
  string,
  Record<string, ModelRegistryEntry[]>
>;

export function useModelRegistry() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.providerSettings.modelRegistry,
    queryFn: () =>
      apiFetch<ModelRegistry>(
        API_ENDPOINTS.providerSettings.modelRegistry,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    staleTime: 1000 * 60 * 30, // 30 min — registry rarely changes
  });
}
