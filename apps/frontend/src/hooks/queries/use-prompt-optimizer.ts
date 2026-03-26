import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { PaginatedResponse } from "@/types/api";

// --- Types ---

export interface EvalDataset {
  id: string;
  name: string;
  description: string;
  bot_id: string | null;
  target_prompt: string;
  test_case_count: number;
  created_at: string;
  updated_at: string;
}

export interface TestCase {
  id: string;
  dataset_id: string;
  user_input: string;
  expected_output: string;
  context?: string;
  created_at: string;
}

export interface OptimizationRun {
  run_id: string;
  bot_id: string;
  dataset_id: string;
  run_type: "optimization" | "validation";
  status: string;
  baseline_score: number;
  best_score: number | null;
  current_iteration: number;
  max_iterations: number;
  stopped_reason: string;
  progress_message: string;
  started_at: string;
  completed_at: string | null;
}

export interface CostEstimate {
  estimated_tokens: number;
  estimated_cost_usd: number;
}

// --- Dataset Queries ---

export function useEvalDatasets(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: [...queryKeys.promptOptimizer.datasets, page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<EvalDataset>>(
        `${API_ENDPOINTS.promptOptimizer.datasets.list}?page=${page}&page_size=${pageSize}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useEvalDataset(id: string) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.promptOptimizer.dataset(id),
    queryFn: () =>
      apiFetch<EvalDataset>(
        API_ENDPOINTS.promptOptimizer.dataset(id),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!id,
  });
}

export function useCreateEvalDataset() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      apiFetch<EvalDataset>(
        API_ENDPOINTS.promptOptimizer.datasets.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.datasets });
    },
  });
}

export function useUpdateEvalDataset() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; name?: string; description?: string }) =>
      apiFetch<EvalDataset>(
        API_ENDPOINTS.promptOptimizer.dataset(id),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.datasets });
    },
  });
}

export function useDeleteEvalDataset() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(
        API_ENDPOINTS.promptOptimizer.dataset(id),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.datasets });
    },
  });
}

// --- Test Case Mutations ---

export function useCreateTestCase() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ datasetId, ...data }: { datasetId: string; user_input: string; expected_output: string; context?: string }) =>
      apiFetch<TestCase>(
        API_ENDPOINTS.promptOptimizer.datasetCases(datasetId),
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.datasets });
    },
  });
}

export function useDeleteTestCase() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ datasetId, caseId }: { datasetId: string; caseId: string }) =>
      apiFetch<void>(
        API_ENDPOINTS.promptOptimizer.datasetCase(datasetId, caseId),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.datasets });
    },
  });
}

// --- Run Queries ---

export function useOptimizationRuns(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: [...queryKeys.promptOptimizer.runs, page, pageSize],
    queryFn: () =>
      apiFetch<PaginatedResponse<OptimizationRun>>(
        `${API_ENDPOINTS.promptOptimizer.runs.list}?page=${page}&page_size=${pageSize}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
  });
}

export function useOptimizationRun(id: string) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: queryKeys.promptOptimizer.run(id),
    queryFn: () =>
      apiFetch<OptimizationRun>(
        API_ENDPOINTS.promptOptimizer.run(id),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!id,
  });
}

/** Polling variant: auto-refetch every 3s while run is active */
export function useOptimizationRunPolling(id: string) {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: [...queryKeys.promptOptimizer.run(id), "polling"],
    queryFn: () =>
      apiFetch<OptimizationRun>(
        API_ENDPOINTS.promptOptimizer.run(id),
        {},
        token ?? undefined,
      ),
    enabled: !!token && !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed" || status === "stopped") {
        return false;
      }
      return 3000;
    },
  });
}

// --- Run Mutations ---

export function useStartOptimization() {
  const token = useAuthStore((s) => s.token);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { bot_id: string; dataset_id: string; max_iterations?: number; patience?: number; budget?: number }) =>
      apiFetch<OptimizationRun>(
        API_ENDPOINTS.promptOptimizer.runs.create,
        { method: "POST", body: JSON.stringify({ ...data, refresh_token: refreshToken ?? "" }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.runs });
    },
  });
}

export function useStopOptimization() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<OptimizationRun>(
        API_ENDPOINTS.promptOptimizer.runStop(id),
        { method: "POST" },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.runs });
    },
  });
}

export function useRollbackRun() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ runId, iteration }: { runId: string; iteration: number }) =>
      apiFetch<OptimizationRun>(
        API_ENDPOINTS.promptOptimizer.runRollback(runId),
        { method: "POST", body: JSON.stringify({ iteration }) },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptOptimizer.runs });
    },
  });
}

export function useRunEval() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (data: { bot_id: string; dataset_id: string }) =>
      apiFetch<unknown>(
        API_ENDPOINTS.promptOptimizer.eval,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useEstimateCost() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (data: {
      dataset_id: string;
      model_id?: string;
      mutator_model_id?: string;
      max_iterations?: number;
      patience?: number;
      budget?: number;
    }) =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      apiFetch<any>(
        API_ENDPOINTS.promptOptimizer.estimate,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
  });
}

// --- Validation Eval ---

export interface ValidationCaseResult {
  case_id: string;
  question: string;
  priority: string;
  pass_rate: number;
  threshold: number;
  passed: boolean;
  unstable: boolean;
  run_scores: number[];
}

export interface ValidationResult {
  dataset_id: string;
  dataset_name: string;
  verdict: "PASS" | "FAIL";
  num_repeats: number;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  unstable_cases: number;
  p0_failures: string[];
  case_results: ValidationCaseResult[];
}

export function useRunValidation() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (data: { dataset_id: string; bot_id?: string; repeats?: number }) =>
      apiFetch<ValidationResult>(
        API_ENDPOINTS.promptOptimizer.validate,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
  });
}

export interface ExchangeRateData {
  from: string;
  to: string;
  rate: number;
  source_date: string;
  fetched_at: string;
}

export function useExchangeRate(target: string = "twd") {
  const token = useAuthStore((s) => s.token);

  return useQuery({
    queryKey: ["exchange-rate", target],
    queryFn: () =>
      apiFetch<ExchangeRateData>(
        `${API_ENDPOINTS.promptOptimizer.exchangeRate}?target=${target}`,
        {},
        token ?? undefined,
      ),
    enabled: !!token,
    staleTime: 1000 * 60 * 30, // 30 min — rate doesn't change often
  });
}
