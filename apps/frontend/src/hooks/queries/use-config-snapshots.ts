/** Issue #60 — 生效設定快照 hooks（trace 面板 / bot 時間軸 / 兩版比較） */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  BotConfigTimeline,
  ConfigSnapshotDiff,
  ConfigSnapshotRecord,
} from "@/types/config-snapshot";

import { queryKeys } from "./keys";

export function useConfigSnapshot(hash: string | null | undefined) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.configSnapshots.detail(hash ?? ""),
    queryFn: () =>
      apiFetch<ConfigSnapshotRecord>(
        API_ENDPOINTS.configSnapshots.detail(hash!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!hash,
    // 快照內容由 hash 決定、不可變 → 不需要重抓
    staleTime: Infinity,
  });
}

export function useConfigSnapshotDiff(
  a: string | null | undefined,
  b: string | null | undefined,
  enabled = true,
) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.configSnapshots.diff(a ?? "", b ?? ""),
    queryFn: () =>
      apiFetch<ConfigSnapshotDiff>(
        API_ENDPOINTS.configSnapshots.diff(a!, b!),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!a && !!b && enabled,
    staleTime: Infinity,
  });
}

export function useBotConfigTimeline(botId: string | null | undefined, limit = 50) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.configSnapshots.botTimeline(botId ?? "", limit),
    queryFn: () =>
      apiFetch<BotConfigTimeline>(
        API_ENDPOINTS.configSnapshots.botTimeline(botId!, limit),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId,
  });
}
