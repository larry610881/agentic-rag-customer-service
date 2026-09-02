/** Issue #60 — 設定變更稽核紀錄 hooks（system_admin only） */

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import type { AuditLogFilters, PaginatedAuditLogs } from "@/types/audit-log";

import { queryKeys } from "./keys";

export function useAuditLogs(filters: AuditLogFilters) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.auditLogs.list(filters),
    queryFn: () =>
      apiFetch<PaginatedAuditLogs>(
        API_ENDPOINTS.auditLogs.list(filters),
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    placeholderData: keepPreviousData,
  });
}
