import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  GuardEffectiveView,
  GuardOverrides,
  GuardSettingsOverview,
  GuardSettingsSaved,
  TenantGuardSettings,
  UpdateTenantGuardRequest,
} from "@/types/guard-stages";

/** GET /admin/guard/settings — system_admin 總覽（平台覆寫、方案、生效預設、可用階段） */
export function useGuardSettingsOverview() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.guardStages.overview,
    queryFn: () =>
      apiFetch<GuardSettingsOverview>(
        API_ENDPOINTS.guardStages.settings,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

/** GET /admin/guard/settings/tenants/{id} — tenant_admin 只能讀自己租戶，system_admin 任意 */
export function useTenantGuardSettings(tenantId: string | null | undefined) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.guardStages.tenant(tenantId ?? ""),
    queryFn: () =>
      apiFetch<TenantGuardSettings>(
        API_ENDPOINTS.guardStages.tenantSettings(tenantId as string),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

/** GET /guard/effective?bot_id= — 某 bot 的有效階段（含 bot 加嚴、鎖定、來源、可用全集） */
export function useGuardEffective(botId: string | null | undefined) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.guardStages.effective(botId ?? ""),
    queryFn: () =>
      apiFetch<GuardEffectiveView>(
        API_ENDPOINTS.guardStages.effective(botId as string),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId,
  });
}

export function useUpdateGuardPlatform() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (overrides: GuardOverrides) =>
      apiFetch<GuardSettingsSaved>(
        API_ENDPOINTS.guardStages.updatePlatform,
        { method: "PUT", body: JSON.stringify({ overrides }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      // 底線 / 預設改變會連動所有租戶與 bot 的有效值
      queryClient.invalidateQueries({ queryKey: queryKeys.guardStages.all });
    },
  });
}

export function useUpdateGuardProfile() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, overrides }: { name: string; overrides: GuardOverrides }) =>
      apiFetch<GuardSettingsSaved>(
        API_ENDPOINTS.guardStages.updateProfile(name),
        { method: "PUT", body: JSON.stringify({ overrides }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.guardStages.all });
    },
  });
}

export function useUpdateGuardTenant() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ tenantId, data }: { tenantId: string; data: UpdateTenantGuardRequest }) =>
      apiFetch<GuardSettingsSaved>(
        API_ENDPOINTS.guardStages.tenantSettings(tenantId),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.guardStages.all });
    },
  });
}
