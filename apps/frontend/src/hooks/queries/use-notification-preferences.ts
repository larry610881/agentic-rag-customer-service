/** Issue #77 — 租戶設定變更通知偏好（tenant_admin 讀寫自己；system_admin 可指定租戶） */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  TenantNotificationPreferences,
  UpdateTenantNotificationPreferencesRequest,
} from "@/types/notification-preferences";

/** GET /tenants/{id}/notification-preferences；tenantId 為 null 時走 "me" */
export function useTenantNotificationPreferences(tenantId: string | null | undefined) {
  const token = useAuthStore((s) => s.token);
  const target = tenantId ?? "me";

  return useQuery({
    queryKey: queryKeys.tenants.notificationPreferences(target),
    queryFn: () =>
      apiFetch<TenantNotificationPreferences>(
        API_ENDPOINTS.tenants.notificationPreferences(target),
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

/** PUT /tenants/{id}/notification-preferences；成功後讓同租戶的偏好失效重抓 */
export function useUpdateTenantNotificationPreferences(tenantId: string | null | undefined) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();
  const target = tenantId ?? "me";

  return useMutation({
    mutationFn: (data: UpdateTenantNotificationPreferencesRequest) =>
      apiFetch<TenantNotificationPreferences>(
        API_ENDPOINTS.tenants.notificationPreferences(target),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.tenants.notificationPreferences(target),
      });
    },
  });
}
