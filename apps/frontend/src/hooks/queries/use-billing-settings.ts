import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  BillingSettings,
  UpdateBillingSettingsRequest,
} from "@/types/billing";

/** Issue #74 — GET /admin/billing/settings（平台匯率 usd_per_point） */
export function useBillingSettings() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.admin.billingSettings,
    queryFn: () =>
      apiFetch<BillingSettings>(
        API_ENDPOINTS.adminBilling.settings,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

/** PUT /admin/billing/settings { usd_per_point } */
export function useUpdateBillingSettings() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateBillingSettingsRequest) =>
      apiFetch<BillingSettings>(
        API_ENDPOINTS.adminBilling.settings,
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.admin.billingSettings });
    },
  });
}
