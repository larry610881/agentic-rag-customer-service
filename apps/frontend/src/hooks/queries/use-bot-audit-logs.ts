/** Issue #71 — 租戶端 bot 變更紀錄（tenant_admin / system_admin） */

import { useInfiniteQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { BotAuditLogPage } from "@/types/bot-audit-log";

export const BOT_AUDIT_LOGS_PAGE_SIZE = 20;

/** GET /bots/{id}/audit-logs — keyset 分頁，next_cursor 為 null 即無下一頁 */
export function useBotAuditLogs(
  botId: string | null | undefined,
  limit = BOT_AUDIT_LOGS_PAGE_SIZE,
) {
  const token = useAuthStore((s) => s.token);

  return useInfiniteQuery({
    queryKey: queryKeys.bots.auditLogs(botId ?? ""),
    queryFn: ({ pageParam }) =>
      apiFetch<BotAuditLogPage>(
        API_ENDPOINTS.bots.auditLogs(botId as string, {
          limit,
          cursor: pageParam,
        }),
        {},
        token ?? undefined,
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: !!token && !!botId,
  });
}
