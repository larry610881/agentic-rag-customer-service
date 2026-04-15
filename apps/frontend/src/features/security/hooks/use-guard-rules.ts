import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api-client";
import { useAuthStore } from "@/stores/use-auth-store";

export interface GuardRuleItem {
  pattern: string;
  type: "regex" | "keyword";
  enabled: boolean;
}

export interface OutputKeywordItem {
  keyword: string;
  enabled: boolean;
}

export interface GuardRulesConfig {
  id: string;
  input_rules: GuardRuleItem[];
  output_keywords: OutputKeywordItem[];
  llm_guard_enabled: boolean;
  llm_guard_model: string;
  input_guard_prompt: string;
  output_guard_prompt: string;
  blocked_response: string;
  updated_at: string;
}

export interface GuardLogItem {
  id: string;
  tenant_id: string;
  bot_id: string | null;
  user_id: string | null;
  log_type: string;
  rule_matched: string;
  user_message: string;
  ai_response: string | null;
  created_at: string;
}

const GUARD_RULES_KEY = ["guard-rules"];
const GUARD_LOGS_KEY = ["guard-logs"];

export function useGuardRules() {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: GUARD_RULES_KEY,
    queryFn: () =>
      apiFetch<GuardRulesConfig>(
        "/api/v1/security/guard-rules",
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useUpdateGuardRules() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<GuardRulesConfig, "id" | "updated_at">) =>
      apiFetch<GuardRulesConfig>(
        "/api/v1/security/guard-rules",
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GUARD_RULES_KEY });
      toast.success("安全規則已更新");
    },
    onError: () => {
      toast.error("更新失敗");
    },
  });
}

export function useResetGuardRules() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiFetch<GuardRulesConfig>(
        "/api/v1/security/guard-rules/reset",
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GUARD_RULES_KEY });
      toast.success("已重置為預設規則");
    },
  });
}

export function useGuardLogs(
  page = 1,
  pageSize = 20,
  logType?: string,
  botId?: string,
) {
  const token = useAuthStore((s) => s.token);

  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (logType) params.set("log_type", logType);
  if (botId) params.set("bot_id", botId);

  return useQuery({
    queryKey: [...GUARD_LOGS_KEY, page, pageSize, logType, botId],
    queryFn: () =>
      apiFetch<{
        items: GuardLogItem[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
      }>(
        `/api/v1/security/guard-logs?${params}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}
