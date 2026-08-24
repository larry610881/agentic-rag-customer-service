/** Issue #54 — Bot 設定版本與發布閘門 hooks */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  ConfigVersion,
  ConfigVersionDetail,
  GateEstimate,
  GateRun,
  VersionMetrics,
} from "@/types/config-version";

import { queryKeys } from "./keys";

interface PaginatedVersions {
  items: ConfigVersion[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function useConfigVersions(botId: string, page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: [...queryKeys.configVersions.list(botId), page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedVersions>(
        API_ENDPOINTS.configVersions.list(botId, page, pageSize),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId,
  });
}

export function useConfigVersion(botId: string, versionId: string) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.configVersions.detail(botId, versionId),
    queryFn: () =>
      apiFetch<ConfigVersionDetail>(
        API_ENDPOINTS.configVersions.detail(botId, versionId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId && !!versionId,
  });
}

export function useVersionMetrics(botId: string, versionId: string) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.configVersions.metrics(botId, versionId),
    queryFn: () =>
      apiFetch<VersionMetrics>(
        API_ENDPOINTS.configVersions.metrics(botId, versionId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId && !!versionId,
  });
}

export function useGateEstimate(botId: string, enabled: boolean) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.configVersions.estimate(botId),
    queryFn: () =>
      apiFetch<GateEstimate>(
        API_ENDPOINTS.promptGate.estimate(botId),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!botId && enabled,
    staleTime: 30_000,
  });
}

/**
 * H18：gate run 轉 completed/error 時 invalidate 版本列表與 detail。
 *
 * useGateRun 完成後只停止輪詢，但 useConfigVersions 列表無輪詢也不會被 invalidate，
 * 導致 version.status 停在 stale 的 "validating"：卡片持續轉圈、發布按鈕永不出現。
 * 傳入 gate run 目前狀態，轉為終態時刷新列表讓 UI 反映 pending_publish/draft。
 */
export function useInvalidateVersionsOnGateComplete(
  botId: string,
  gateRunStatus: string | null | undefined,
) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (gateRunStatus === "completed" || gateRunStatus === "error") {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.configVersions.list(botId),
      });
    }
  }, [gateRunStatus, botId, queryClient]);
}

/** Gate run polling：3s 刷新，completed/error 停止 */
export function useGateRun(runId: string | null) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: queryKeys.configVersions.gateRun(runId ?? ""),
    queryFn: () =>
      apiFetch<GateRun>(
        API_ENDPOINTS.promptGate.run(runId ?? ""),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!runId,
    refetchInterval: (query) => {
      // L16：查詢本身失敗（404/500）時 data 恆 undefined，若不先判斷 error
      // 會對已確定失敗的 run id 每 3 秒無限輪詢直到使用者離開
      if (query.state.status === "error") return false;
      const status = query.state.data?.status;
      return status === "completed" || status === "error" ? false : 3000;
    },
  });
}

function useVersionMutation<TVariables>(
  makeRequest: (
    vars: TVariables,
    token: string | undefined,
  ) => Promise<unknown>,
  botIdOf: (vars: TVariables) => string,
) {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vars: TVariables) => makeRequest(vars, token ?? undefined),
    onSuccess: (_data, vars) => {
      const botId = botIdOf(vars);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.configVersions.list(botId),
      });
      // M40：publish/rollback 會把版本快照 apply 回 bot 本體並清後端 cache。若不刷新
      // bots.detail，使用者切到 bot-detail 頁會吃到 staleTime 內的舊 prompt，誤以為
      // 沒生效而按儲存 → PUT 舊值覆寫剛發布的設定。
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bots.detail(botId),
      });
      if (tenantId) {
        void queryClient.invalidateQueries({
          queryKey: queryKeys.bots.all(tenantId),
        });
      }
    },
  });
}

export function useCreateConfigVersion() {
  return useVersionMutation(
    (vars: { botId: string; changes: Record<string, unknown> }, token) =>
      apiFetch<ConfigVersionDetail>(
        API_ENDPOINTS.configVersions.create(vars.botId),
        {
          method: "POST",
          body: JSON.stringify({ changes: vars.changes }),
        },
        token,
      ),
    (vars) => vars.botId,
  );
}

export function usePublishConfigVersion() {
  return useVersionMutation(
    (vars: { botId: string; versionId: string; force?: boolean }, token) =>
      apiFetch<ConfigVersion>(
        API_ENDPOINTS.configVersions.publish(vars.botId, vars.versionId),
        {
          method: "POST",
          body: JSON.stringify({ force: vars.force ?? false }),
        },
        token,
      ),
    (vars) => vars.botId,
  );
}

export function useRejectConfigVersion() {
  return useVersionMutation(
    (vars: { botId: string; versionId: string }, token) =>
      apiFetch<ConfigVersion>(
        API_ENDPOINTS.configVersions.reject(vars.botId, vars.versionId),
        { method: "POST" },
        token,
      ),
    (vars) => vars.botId,
  );
}

export function useRollbackConfigVersion() {
  return useVersionMutation(
    (vars: { botId: string; targetVersionId: string }, token) =>
      apiFetch<ConfigVersion>(
        API_ENDPOINTS.configVersions.rollback(vars.botId),
        {
          method: "POST",
          body: JSON.stringify({ target_version_id: vars.targetVersionId }),
        },
        token,
      ),
    (vars) => vars.botId,
  );
}

export function useReplayCompare() {
  return useVersionMutation(
    (
      vars: { botId: string; versionId: string; sampleSize?: number },
      token,
    ) =>
      apiFetch<GateRun>(
        API_ENDPOINTS.configVersions.replayCompare(
          vars.botId,
          vars.versionId,
        ),
        {
          method: "POST",
          body: JSON.stringify({
            sample_size: vars.sampleSize ?? 10,
            // H3：背景任務長 run 中途 access token 過期時可用 refresh_token 續期
            refresh_token: useAuthStore.getState().refreshToken ?? "",
          }),
        },
        token,
      ),
    (vars) => vars.botId,
  );
}


export function useValidateConfigVersion() {
  return useVersionMutation(
    (vars: { botId: string; versionId: string }, token) =>
      apiFetch<GateRun>(
        API_ENDPOINTS.configVersions.validate(vars.botId, vars.versionId),
        {
          method: "POST",
          // H3：長 gate run 可能超過 access token 15 分鐘壽命，帶 refresh_token 供續期
          body: JSON.stringify({
            refresh_token: useAuthStore.getState().refreshToken ?? "",
          }),
        },
        token,
      ),
    (vars) => vars.botId,
  );
}
