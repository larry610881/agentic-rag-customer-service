// HARDCODE - 地端模型 A/B 測試用 hooks，正式上線前移除整個檔案
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";

export interface AbPreset {
  label: string;
  model: string;
  description: string;
}

export interface ModelStatusResponse {
  model: string;
  status: "ready" | "not_loaded" | "unreachable";
}

export function useOllamaAbPresets() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["ollama", "ab-presets"],
    queryFn: () =>
      apiFetch<AbPreset[]>(API_ENDPOINTS.ollama.abPresets, {}, token ?? undefined),
    staleTime: Infinity,
  });
}

export function useOllamaModelStatus(model: string | null, enabled = true) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["ollama", "model-status", model],
    queryFn: () =>
      apiFetch<ModelStatusResponse>(
        API_ENDPOINTS.ollama.modelStatus(model!),
        {},
        token ?? undefined,
      ),
    enabled: !!model && enabled,
    refetchInterval: (query) => {
      // 當模型還未就緒時，每 5 秒 polling 一次
      const status = query.state.data?.status;
      return status === "ready" ? false : 5000;
    },
    staleTime: 0,
  });
}
