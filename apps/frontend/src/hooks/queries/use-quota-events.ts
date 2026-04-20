import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";

export interface QuotaEventItem {
  event_id: string;
  event_type: string; // 'auto_topup' | 'base_warning_80' | 'base_exhausted_100'
  tenant_id: string;
  tenant_name: string;
  cycle_year_month: string;
  created_at: string;
  addon_tokens_added: number | null;
  amount_currency: string | null;
  amount_value: string | null; // Decimal serialized as string
  used_ratio: string | null;
  message: string | null;
  reason: string | null;
}

export interface PaginatedQuotaEvents {
  items: QuotaEventItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface UseQuotaEventsParams {
  tenantId?: string;
  page?: number;
  pageSize?: number;
  enabled?: boolean;
}

/**
 * 系統管理員專用：取得自動續約 + 額度警示合併時間軸事件。
 * 跨表合併（BillingTransaction + QuotaAlertLog），按 created_at desc。
 */
export function useQuotaEvents({
  tenantId,
  page = 1,
  pageSize = 20,
  enabled = true,
}: UseQuotaEventsParams = {}) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.admin.quotaEvents(tenantId ?? "all", page, pageSize),
    queryFn: () =>
      apiFetch<PaginatedQuotaEvents>(
        API_ENDPOINTS.adminQuotaEvents.list({ tenantId, page, pageSize }),
        {},
        token ?? undefined,
      ),
    enabled: !!token && enabled,
    staleTime: 30_000,
  });
}
