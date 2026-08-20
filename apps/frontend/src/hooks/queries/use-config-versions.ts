/** Issue #54 — Bot 設定版本與發布閘門 hooks */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vars: TVariables) => makeRequest(vars, token ?? undefined),
    onSuccess: (_data, vars) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.configVersions.list(botIdOf(vars)),
      });
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
          body: JSON.stringify({ sample_size: vars.sampleSize ?? 10 }),
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
        { method: "POST" },
        token,
      ),
    (vars) => vars.botId,
  );
}
