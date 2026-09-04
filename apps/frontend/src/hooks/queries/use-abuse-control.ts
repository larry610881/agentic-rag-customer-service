import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  AbuseControlItem,
  AbuseOverrides,
  AbuseSettingsOverview,
  AbuseSettingsSaved,
  ReleaseAbuseControlRequest,
  TenantAbuseSettings,
  UpdateTenantAbuseSettingsRequest,
} from "@/types/abuse-control";

/** 受控清單每 30 秒自動更新 */
export const ABUSE_CONTROLS_REFETCH_MS = 30_000;

/** GET /settings — system_admin 總覽（平台覆寫、方案、生效預設、鍵與範圍） */
export function useAbuseSettingsOverview() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.abuseControl.overview,
    queryFn: () =>
      apiFetch<AbuseSettingsOverview>(
        API_ENDPOINTS.abuseControl.settings,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

/** GET /settings/tenants/{id} — tenant_admin 只能讀自己租戶，system_admin 任意 */
export function useTenantAbuseSettings(tenantId: string | null | undefined) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.abuseControl.tenant(tenantId ?? ""),
    queryFn: () =>
      apiFetch<TenantAbuseSettings>(
        API_ENDPOINTS.abuseControl.tenantSettings(tenantId as string),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!tenantId,
  });
}

export function useUpdatePlatformAbuseSettings() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (overrides: AbuseOverrides) =>
      apiFetch<AbuseSettingsSaved>(
        API_ENDPOINTS.abuseControl.updatePlatform,
        { method: "PUT", body: JSON.stringify({ overrides }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      // 平台預設改變會連動所有租戶的 effective
      queryClient.invalidateQueries({ queryKey: ["abuse-control", "settings"] });
    },
  });
}

export function useUpdateAbuseProfile() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      name,
      overrides,
    }: {
      name: string;
      overrides: AbuseOverrides;
    }) =>
      apiFetch<AbuseSettingsSaved>(
        API_ENDPOINTS.abuseControl.updateProfile(name),
        { method: "PUT", body: JSON.stringify({ overrides }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["abuse-control", "settings"] });
    },
  });
}

export function useUpdateTenantAbuseSettings() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      tenantId,
      data,
    }: {
      tenantId: string;
      data: UpdateTenantAbuseSettingsRequest;
    }) =>
      apiFetch<AbuseSettingsSaved>(
        API_ENDPOINTS.abuseControl.tenantSettings(tenantId),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: (_data, { tenantId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.abuseControl.tenant(tenantId),
      });
    },
  });
}

/** GET /controls — tenant_admin 只看自己租戶（後端強制），system_admin 可篩選 */
export function useAbuseControls(tenantId?: string) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.abuseControl.controls(tenantId),
    queryFn: () =>
      apiFetch<AbuseControlItem[]>(
        API_ENDPOINTS.abuseControl.controls(tenantId),
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    refetchInterval: ABUSE_CONTROLS_REFETCH_MS,
    placeholderData: (prev) => prev,
  });
}

export function useReleaseAbuseControl() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ReleaseAbuseControlRequest) =>
      apiFetch<void>(
        API_ENDPOINTS.abuseControl.release,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["abuse-control", "controls"] });
    },
  });
}
