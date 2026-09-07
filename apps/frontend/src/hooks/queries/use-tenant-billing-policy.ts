import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  TenantBillingPolicyResponse,
  UpdateTenantBillingPolicyRequest,
} from "@/types/billing";

/**
 * Issue #74 — PUT /tenants/{tenant_id}/billing-policy（tenant_id 可為 "me"）
 * 方案不允許租戶自改時後端回 403；成功後讓本租戶的額度快照失效重抓。
 */
export function useUpdateTenantBillingPolicy(tenantId: string | null) {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateTenantBillingPolicyRequest) =>
      apiFetch<TenantBillingPolicyResponse>(
        API_ENDPOINTS.tenants.billingPolicy(tenantId ?? "me"),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      if (tenantId) {
        qc.invalidateQueries({ queryKey: queryKeys.tenants.quota(tenantId) });
      }
    },
  });
}
