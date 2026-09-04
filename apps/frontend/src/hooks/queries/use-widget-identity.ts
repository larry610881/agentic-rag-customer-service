import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  UpdateWidgetIdentityPolicyRequest,
  WidgetIdentityRotated,
  WidgetIdentityStatus,
} from "@/types/widget-identity";

/**
 * GET /widget-identity/secret — tenant_admin 不帶 tenantId（後端取自 token）；
 * system_admin 必帶 tenantId（後端 422），所以 system_admin 未選租戶時呼叫端應傳 enabled=false。
 */
export function useWidgetIdentityStatus(tenantId?: string, enabled = true) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.widgetIdentity.status(tenantId),
    queryFn: () =>
      apiFetch<WidgetIdentityStatus>(
        API_ENDPOINTS.widgetIdentity.secret(tenantId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && enabled,
  });
}

/** POST /widget-identity/secret/rotate — 回傳的 secret 只有這一次 */
export function useRotateWidgetIdentitySecret() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ tenantId }: { tenantId?: string }) =>
      apiFetch<WidgetIdentityRotated>(
        API_ENDPOINTS.widgetIdentity.rotate(tenantId),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: (_data, { tenantId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.widgetIdentity.status(tenantId),
      });
    },
  });
}

/** PUT /widget-identity/secret — 只送有變更的欄位；回應即最新狀態 */
export function useUpdateWidgetIdentityPolicy() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      tenantId,
      data,
    }: {
      tenantId?: string;
      data: UpdateWidgetIdentityPolicyRequest;
    }) =>
      apiFetch<WidgetIdentityStatus>(
        API_ENDPOINTS.widgetIdentity.secret(tenantId),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: (data, { tenantId }) => {
      const key = queryKeys.widgetIdentity.status(tenantId);
      queryClient.setQueryData(key, data);
      queryClient.invalidateQueries({ queryKey: key });
    },
  });
}
