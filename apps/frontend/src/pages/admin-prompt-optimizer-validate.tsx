import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, ShieldAlert, AlertTriangle, Loader2, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ROUTES } from "@/routes/paths";
import { useAuthStore } from "@/stores/use-auth-store";
import { useTenants } from "@/hooks/queries/use-tenants";
import { useBots } from "@/hooks/queries/use-bots";
import {
  useEvalDatasets,
  useEstimateCost,
  useRunValidation,
  useExchangeRate,
} from "@/hooks/queries/use-prompt-optimizer";
import type {
  ValidationResult,
  ValidationCaseResult,
} from "@/hooks/queries/use-prompt-optimizer";

const REPEAT_OPTIONS = [3, 5, 10];

function PassRateBadge({ result }: { result: ValidationCaseResult }) {
  const pct = Math.round(result.pass_rate * 100);
  if (!result.passed) {
    return <Badge variant="destructive">{pct}%</Badge>;
  }
  if (result.unstable) {
    return (
      <Badge variant="outline" className="border-yellow-500 text-yellow-600">
        {pct}%
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="border-green-500 text-green-600">
      {pct}%
    </Badge>
  );
}

export default function AdminPromptOptimizerValidatePage() {
  const navigate = useNavigate();
  const role = useAuthStore((s) => s.role);
  const isSystemAdmin = role === "system_admin";

  // Form state
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [selectedBotId, setSelectedBotId] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [repeats, setRepeats] = useState(5);

  // Queries
  const { data: tenantsData } = useTenants(1, 100);
  const { data: botsData } = useBots(1, 100);
  const { data: datasetsData } = useEvalDatasets(1, 100);
  const { data: exchangeRate } = useExchangeRate("twd");

  // Mutations
  const estimateCost = useEstimateCost();
  const validation = useRunValidation();
  const result = validation.data as ValidationResult | undefined;

  const tenants = tenantsData?.items ?? [];
  const bots = botsData?.items ?? [];
  const datasets = datasetsData?.items ?? [];

  const canStart = selectedBotId && selectedDatasetId;

  const toTWD = (usd: number | undefined) => {
    if (usd == null || !exchangeRate?.rate) return null;
    return `NT$${(usd * exchangeRate.rate).toFixed(0)}`;
  };

  const selectedBot = bots.find((b) => b.id === selectedBotId);
  const botModelId = selectedBot?.llm_model || "";

  const handleEstimate = () => {
    if (!selectedDatasetId) return;
    estimateCost.mutate({
      dataset_id: selectedDatasetId,
      bot_id: selectedBotId || undefined,
      model_id: botModelId,
      max_iterations: 0,
      patience: 0,
      budget: 0,
    });
  };

  const handleStart = () => {
    if (!canStart) return;
    validation.mutate(
      { dataset_id: selectedDatasetId, bot_id: selectedBotId, repeats },
      {
        onSuccess: (data) => {
          const v = data as ValidationResult;
          if (v.verdict === "PASS") {
            toast.success(`驗收通過 (${v.passed_cases}/${v.total_cases})`);
          } else {
            toast.error(`驗收未通過 (${v.passed_cases}/${v.total_cases})`);
          }
        },
        onError: () => toast.error("驗收評估失敗"),
      },
    );
  };

  // Validation-specific cost: repeats × cases × eval_cost_per_call
  const evalCostPerCall = estimateCost.data?.eval_cost_per_call ?? 0;
  const numCases = estimateCost.data?.num_cases ?? 0;
  const totalCalls = repeats * numCases;
  const totalCostUsd = totalCalls * evalCostPerCall;

  return (
    <div className="space-y-6 p-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="mb-2"
          onClick={() => navigate(ROUTES.ADMIN_PROMPT_OPTIMIZER)}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回 Prompt 自動優化
        </Button>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <ShieldCheck className="h-6 w-6" />
          驗收評估
        </h1>
        <p className="mt-1 text-muted-foreground">
          對 prompt 重複執行 N 次評估，統計 pass rate 判定穩定性
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left column: Target selection */}
        <Card>
          <CardHeader>
            <CardTitle>評估目標</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {isSystemAdmin && (
              <div className="space-y-2">
                <Label>租戶</Label>
                <Select
                  value={selectedTenantId}
                  onValueChange={(v) => {
                    setSelectedTenantId(v);
                    setSelectedBotId("");
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="選擇租戶" />
                  </SelectTrigger>
                  <SelectContent>
                    {tenants.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label>Bot</Label>
              <Select
                value={selectedBotId}
                onValueChange={setSelectedBotId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="選擇 Bot" />
                </SelectTrigger>
                <SelectContent>
                  {bots.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>情境集</Label>
              <Select
                value={selectedDatasetId}
                onValueChange={setSelectedDatasetId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="選擇情境集" />
                </SelectTrigger>
                <SelectContent>
                  {datasets.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name} ({d.test_case_count} 個案例)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>重複次數</Label>
              <Select
                value={String(repeats)}
                onValueChange={(v) => setRepeats(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REPEAT_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n} 次
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                每個 case 重複評估 N 次，統計 pass rate
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Right column: Cost estimate */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>費用估算</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                variant="outline"
                onClick={handleEstimate}
                disabled={!canStart || estimateCost.isPending}
              >
                {estimateCost.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                估算費用
              </Button>

              {estimateCost.data && (
                <div className="space-y-2 rounded-md border p-4 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">情境集</span>
                    <span className="font-medium">
                      {estimateCost.data.dataset_name}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">測試案例數</span>
                    <span className="font-medium">
                      {estimateCost.data.num_cases} 個
                    </span>
                  </div>
                  {estimateCost.data.model_id && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">評估模型</span>
                      <span className="font-medium">
                        {estimateCost.data.model_id}
                        {estimateCost.data.eval_model_pricing && (
                          <span className="ml-1 text-xs text-muted-foreground">
                            (${estimateCost.data.eval_model_pricing.input_per_1m}/
                            ${estimateCost.data.eval_model_pricing.output_per_1m} per 1M)
                          </span>
                        )}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">每次評估呼叫</span>
                    <span className="font-medium">
                      USD ${estimateCost.data.eval_cost_per_call?.toFixed(4) ?? "—"}
                    </span>
                  </div>

                  {/* Token Breakdown */}
                  {estimateCost.data.token_breakdown && (
                    <>
                      <div className="my-1 border-t" />
                      <p className="text-xs font-medium text-muted-foreground">
                        Token 估算明細
                      </p>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs">
                        <span className="text-muted-foreground">系統 Prompt</span>
                        <span>{estimateCost.data.token_breakdown.prompt_tokens} tokens</span>
                        <span className="text-muted-foreground">
                          RAG Context（top_k={estimateCost.data.token_breakdown.rag_top_k}）
                        </span>
                        <span>+{estimateCost.data.token_breakdown.rag_context_tokens} tokens</span>
                        <span className="text-muted-foreground">平均問題長度</span>
                        <span>+{estimateCost.data.token_breakdown.avg_question_tokens} tokens</span>
                        {(estimateCost.data.token_breakdown.avg_history_tokens ?? 0) > 0 && (
                          <>
                            <span className="text-muted-foreground">平均對話歷史</span>
                            <span>+{estimateCost.data.token_breakdown.avg_history_tokens} tokens</span>
                          </>
                        )}
                        <span className="text-muted-foreground">加權平均 input</span>
                        <span className="font-medium text-primary">
                          {estimateCost.data.token_breakdown.weighted_avg_input} tokens
                        </span>
                        <span className="text-muted-foreground">估算 output</span>
                        <span>{estimateCost.data.token_breakdown.output_tokens} tokens</span>
                      </div>
                    </>
                  )}

                  <div className="my-1 border-t" />
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      驗收費用（{repeats} 次 × {numCases} cases）
                    </span>
                    <span className="font-medium text-primary">
                      USD ${totalCostUsd.toFixed(4)}
                      {toTWD(totalCostUsd) && (
                        <span className="ml-1 text-xs font-normal text-muted-foreground">
                          ({toTWD(totalCostUsd)})
                        </span>
                      )}
                    </span>
                  </div>

                  {exchangeRate && (
                    <div className="mt-2 flex items-center justify-end gap-1 text-[11px] text-muted-foreground">
                      <span>匯率 1 USD = {exchangeRate.rate.toFixed(2)} TWD</span>
                      <span>·</span>
                      <span>更新：{exchangeRate.source_date}</span>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Start button */}
      <div className="flex justify-end">
        <Button
          size="lg"
          onClick={handleStart}
          disabled={!canStart || validation.isPending}
        >
          {validation.isPending && (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          )}
          開始驗收
        </Button>
      </div>

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Verdict Banner */}
          <div
            className={`flex items-center gap-3 rounded-lg border p-4 ${
              result.verdict === "PASS"
                ? "border-green-200 bg-green-50"
                : "border-red-200 bg-red-50"
            }`}
          >
            {result.verdict === "PASS" ? (
              <ShieldCheck className="h-8 w-8 text-green-600" />
            ) : (
              <ShieldAlert className="h-8 w-8 text-red-600" />
            )}
            <div>
              <p className="text-lg font-bold">
                {result.verdict === "PASS" ? "PASS" : "FAIL"}
              </p>
              <p className="text-sm text-muted-foreground">
                {result.passed_cases}/{result.total_cases} cases 通過
                {result.unstable_cases > 0 &&
                  ` (${result.unstable_cases} 不穩定)`}
                {" · "}重複 {result.num_repeats} 次
              </p>
            </div>
          </div>

          {/* P0 Failures */}
          {result.p0_failures.length > 0 && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="font-semibold text-red-700 mb-1">P0 安全案例失敗</p>
              {result.p0_failures.map((cid) => {
                const cr = result.case_results.find((c) => c.case_id === cid);
                return (
                  <p key={cid} className="text-sm text-red-600">
                    {cid} — pass rate{" "}
                    {cr ? `${Math.round(cr.pass_rate * 100)}%` : "N/A"} (需 100%)
                  </p>
                );
              })}
            </div>
          )}

          {/* Unstable Warning */}
          {result.unstable_cases > 0 && (
            <div className="flex items-center gap-2 rounded-lg border border-yellow-200 bg-yellow-50 p-3">
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
              <p className="text-sm text-yellow-700">
                {result.unstable_cases} 個案例通過但不穩定（pass rate &lt; 100%），建議觀察
              </p>
            </div>
          )}

          {/* Case Results Table */}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">優先級</TableHead>
                <TableHead>Case ID</TableHead>
                <TableHead className="max-w-[300px]">問題</TableHead>
                <TableHead className="w-[80px]">Pass Rate</TableHead>
                <TableHead className="w-[60px]">門檻</TableHead>
                <TableHead className="w-[60px]">結果</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.case_results.map((cr) => (
                <TableRow
                  key={cr.case_id}
                  className={
                    !cr.passed
                      ? "bg-red-50/50"
                      : cr.unstable
                        ? "bg-yellow-50/50"
                        : ""
                  }
                >
                  <TableCell>
                    <Badge variant={cr.priority === "P0" ? "destructive" : "outline"}>
                      {cr.priority}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{cr.case_id}</TableCell>
                  <TableCell className="max-w-[300px] truncate text-sm">
                    {cr.question}
                  </TableCell>
                  <TableCell>
                    <PassRateBadge result={cr} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {Math.round(cr.threshold * 100)}%
                  </TableCell>
                  <TableCell>
                    {cr.passed ? (
                      cr.unstable ? (
                        <AlertTriangle className="h-4 w-4 text-yellow-500" />
                      ) : (
                        <ShieldCheck className="h-4 w-4 text-green-500" />
                      )
                    ) : (
                      <ShieldAlert className="h-4 w-4 text-red-500" />
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
