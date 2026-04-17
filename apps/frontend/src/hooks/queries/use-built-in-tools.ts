import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";

export interface BuiltInTool {
  name: string;
  label: string;
  description: string;
  requires_kb: boolean;
  /** 僅 system_admin 呼叫時由後端附上 */
  scope?: "global" | "tenant";
  /** 僅 system_admin 呼叫時由後端附上 */
  tenant_ids?: string[];
}

/**
 * 取 current user 可用 built-in tools（後端自動依 tenant 過濾）。
 * 系統管理員切換 scope 後會 invalidate 此 queryKey，確保 Bot 編輯頁即時更新。
 */
export function useBuiltInTools() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);

  return useQuery({
    queryKey: ["built-in-tools", tenantId ?? "anon"],
    queryFn: () =>
      apiFetch<BuiltInTool[]>(
        API_ENDPOINTS.builtInTools.list,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    // 一般用戶短期 cache（60 秒）即可；admin 改動後觸發 invalidation
    staleTime: 60_000,
  });
}
