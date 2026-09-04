import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { StructuredOutputCapability } from "@/types/llm-capability";

/** 能力表變動極少，5 分鐘內不重查 */
export const STRUCTURED_OUTPUT_CAPABILITY_STALE_MS = 5 * 60 * 1000;

/**
 * Issue #70 — GET /llm/structured-output-capability?provider=&model=
 * provider / model 任一為空時不發請求（表單尚未選模型）。
 */
export function useStructuredOutputCapability(
  provider?: string,
  model?: string,
) {
  const token = useAuthStore((s) => s.token);
  const ready = !!provider && !!model;

  return useQuery({
    queryKey: queryKeys.llm.structuredOutputCapability(
      provider ?? "",
      model ?? "",
    ),
    queryFn: () =>
      apiFetch<StructuredOutputCapability>(
        API_ENDPOINTS.llm.structuredOutputCapability(
          provider as string,
          model as string,
        ),
        {},
        token ?? undefined,
      ),
    enabled: !!token && ready,
    staleTime: STRUCTURED_OUTPUT_CAPABILITY_STALE_MS,
  });
}
