import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Wand2, Loader2, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ModelSelect } from "@/components/shared/model-select";
import { ROUTES } from "@/routes/paths";
import { useAuthStore } from "@/stores/use-auth-store";
import { useTenants } from "@/hooks/queries/use-tenants";
import { useBots } from "@/hooks/queries/use-bots";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import {
  useEvalDatasets,
  useEstimateCost,
  useStartOptimization,
} from "@/hooks/queries/use-prompt-optimizer";
import { useExchangeRate } from "@/hooks/queries/use-prompt-optimizer";
import { CascadeModeSelector } from "@/features/admin/components/prompt-optimizer/cascade-mode-selector";

export default function AdminPromptOptimizerStartPage() {
  const navigate = useNavigate();
  const role = useAuthStore((s) => s.role);
  const isSystemAdmin = role === "system_admin";

  // Form state
  const [selectedTenantId, setSelectedTenantId] = useState<string>("");
  const [selectedBotId, setSelectedBotId] = useState<string>("");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [optimizationMode, setOptimizationMode] = useState<
    "single" | "cascade"
  >("single");
  const [targetField, setTargetField] = useState<string>("system_prompt");
  const [maxIterations, setMaxIterations] = useState(10);
  const [patience, setPatience] = useState(3);
  const [tokenBudget, setTokenBudget] = useState(100000);
  const [selectedModel, setSelectedModel] = useState<string>("");

  // Queries
  const { data: tenantsData } = useTenants(1, 100);
  const { data: botsData } = useBots(1, 100);
  const { data: datasetsData } = useEvalDatasets(1, 100);
  const { data: enabledModels } = useEnabledModels();

  // Exchange rate
  const { data: exchangeRate } = useExchangeRate("twd");

  // Mutations
  const estimateCost = useEstimateCost();
  const startOptimization = useStartOptimization();

  const tenants = tenantsData?.items ?? [];
  const bots = botsData?.items ?? [];
  const datasets = datasetsData?.items ?? [];
  const models = enabledModels ?? [];

  const canStart = selectedBotId && selectedDatasetId;

  /** Convert USD to TWD string */
  const toTWD = (usd: number | undefined) => {
    if (usd == null || !exchangeRate?.rate) return null;
    return `NT$${(usd * exchangeRate.rate).toFixed(0)}`;
  };

  // Find selected bot's model for eval cost estimation
  const selectedBot = bots.find((b) => b.id === selectedBotId);
  const botModelId = selectedBot?.llm_model || "";

  const handleEstimate = () => {
    if (!selectedDatasetId) return;
    estimateCost.mutate({
      dataset_id: selectedDatasetId,
      bot_id: selectedBotId || undefined,
      model_id: botModelId,
      mutator_model_id: selectedModel || undefined,
      max_iterations: maxIterations,
      patience,
      budget: tokenBudget,
    });
  };

  const handleStart = () => {
    if (!canStart) return;
    startOptimization.mutate(
      {
        bot_id: selectedBotId,
        dataset_id: selectedDatasetId,
        max_iterations: maxIterations,
        patience,
        budget: tokenBudget,
        ...(selectedModel ? { mutator_model: selectedModel } : {}),
      },
      {
        onSuccess: (run) => {
          toast.success("優化已啟動");
          navigate(
            ROUTES.ADMIN_PROMPT_OPTIMIZER_RUN_DETAIL.replace(
              ":runId",
              run.run_id,
            ),
          );
        },
        onError: () => {
          toast.error("啟動優化失敗");
        },
      },
    );
  };

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
          <Wand2 className="h-6 w-6" />
          啟動優化
        </h1>
        <p className="mt-1 text-muted-foreground">
          選擇 Bot 與情境集，設定參數後開始自動優化
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left column: Target selection */}
        <Card>
          <CardHeader>
            <CardTitle>優化目標</CardTitle>
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

            <CascadeModeSelector
              value={optimizationMode}
              onChange={setOptimizationMode}
              targetField={targetField}
              onTargetFieldChange={setTargetField}
            />
          </CardContent>
        </Card>

        {/* Right column: Parameters */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>進階設定</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>最大迭代次數</Label>
                  <Input
                    type="number"
                    min={1}
                    max={50}
                    value={maxIterations}
                    onChange={(e) =>
                      setMaxIterations(Number(e.target.value) || 1)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>耐心值</Label>
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={patience}
                    onChange={(e) =>
                      setPatience(Number(e.target.value) || 1)
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    連續無改善次數後停止
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Token 預算上限</Label>
                <Input
                  type="number"
                  min={1000}
                  step={10000}
                  value={tokenBudget}
                  onChange={(e) =>
                    setTokenBudget(Number(e.target.value) || 1000)
                  }
                />
                <p className="text-xs text-muted-foreground">
                  總 token 用量上限
                </p>
              </div>

              <div className="space-y-2">
                <Label>Mutator 模型</Label>
                <ModelSelect
                  value={
                    selectedModel
                      ? (models.find((m) => m.model_id === selectedModel)
                          ? `${models.find((m) => m.model_id === selectedModel)!.provider_name}:${selectedModel}`
                          : "")
                      : ""
                  }
                  onValueChange={(combined) => {
                    if (combined === "__none__") {
                      setSelectedModel("");
                    } else {
                      const [, modelId] = combined.split(":");
                      setSelectedModel(modelId);
                    }
                  }}
                  enabledModels={enabledModels}
                  allowEmpty
                  placeholder="選擇模型（用於生成優化提示詞）"
                />
                <p className="text-xs text-muted-foreground">
                  用於分析失敗案例並生成改進版提示詞的 LLM 模型。建議選擇性價比高的模型。
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Cost estimate */}
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
                      <span className="text-muted-foreground">
                        評估模型
                      </span>
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
                  {estimateCost.data.mutator_model_id &&
                    estimateCost.data.mutator_model_id !==
                      estimateCost.data.model_id && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">
                          Mutator 模型
                        </span>
                        <span className="font-medium">
                          {estimateCost.data.mutator_model_id}
                          {estimateCost.data.mutator_model_pricing && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              (${estimateCost.data.mutator_model_pricing.input_per_1m}/
                              ${estimateCost.data.mutator_model_pricing.output_per_1m} per 1M)
                            </span>
                          )}
                        </span>
                      </div>
                    )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      每次評估呼叫
                    </span>
                    <span className="font-medium">
                      USD ${estimateCost.data.eval_cost_per_call?.toFixed(4) ?? "—"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      每次 Mutator 呼叫
                    </span>
                    <span className="font-medium">
                      USD ${estimateCost.data.mutator_cost_per_call?.toFixed(4) ?? "—"}
                    </span>
                  </div>
                  <div className="my-1 border-t" />
                  {/* Token Breakdown */}
                  {estimateCost.data.token_breakdown && (
                    <>
                      <div className="my-1 border-t" />
                      <p className="text-xs font-medium text-muted-foreground">
                        Token 估算明細
                      </p>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs">
                        <span className="text-muted-foreground">
                          系統 Prompt
                        </span>
                        <span>
                          {estimateCost.data.token_breakdown.prompt_tokens} tokens
                        </span>
                        <span className="text-muted-foreground">
                          RAG Context（top_k={estimateCost.data.token_breakdown.rag_top_k}）
                        </span>
                        <span>
                          +{estimateCost.data.token_breakdown.rag_context_tokens} tokens
                        </span>
                        <span className="text-muted-foreground">
                          平均問題長度
                        </span>
                        <span>
                          +{estimateCost.data.token_breakdown.avg_question_tokens} tokens
                        </span>
                        {(estimateCost.data.token_breakdown.avg_history_tokens ?? 0) > 0 && (
                          <>
                            <span className="text-muted-foreground">
                              平均對話歷史
                            </span>
                            <span>
                              +{estimateCost.data.token_breakdown.avg_history_tokens} tokens
                            </span>
                          </>
                        )}
                        <span className="text-muted-foreground">
                          有 RAG 的 input
                        </span>
                        <span className="font-medium">
                          {estimateCost.data.token_breakdown.input_with_rag} tokens
                        </span>
                        <span className="text-muted-foreground">
                          無 RAG 的 input
                        </span>
                        <span>
                          {estimateCost.data.token_breakdown.input_without_rag} tokens
                        </span>
                        <span className="text-muted-foreground">
                          RAG 案例佔比
                        </span>
                        <span>
                          {Math.round(estimateCost.data.token_breakdown.rag_case_ratio * 100)}%
                          （{estimateCost.data.token_breakdown.rag_case_count}/{estimateCost.data.token_breakdown.rag_case_count + estimateCost.data.token_breakdown.no_rag_case_count}）
                        </span>
                        <span className="text-muted-foreground">
                          加權平均 input
                        </span>
                        <span className="font-medium text-primary">
                          {estimateCost.data.token_breakdown.weighted_avg_input} tokens
                        </span>
                        <span className="text-muted-foreground">
                          估算 output
                        </span>
                        <span>
                          {estimateCost.data.token_breakdown.output_tokens} tokens
                        </span>
                      </div>
                    </>
                  )}

                  <div className="my-1 border-t" />
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Baseline 費用</span>
                    <span className="font-medium">
                      USD ${estimateCost.data.baseline_cost?.toFixed(2)}
                      {toTWD(estimateCost.data.baseline_cost) && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          ({toTWD(estimateCost.data.baseline_cost)})
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      最低預估（{estimateCost.data.min_estimate?.iterations}{" "}
                      輪收斂）
                    </span>
                    <span className="font-medium text-green-600">
                      USD ${estimateCost.data.min_estimate?.cost?.toFixed(2)}
                      {toTWD(estimateCost.data.min_estimate?.cost) && (
                        <span className="ml-1 text-xs font-normal text-muted-foreground">
                          ({toTWD(estimateCost.data.min_estimate?.cost)})
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      最高預估（{estimateCost.data.max_estimate?.iterations}{" "}
                      輪 / budget 上限）
                    </span>
                    <span className="font-medium text-yellow-600">
                      USD ${estimateCost.data.max_estimate?.cost?.toFixed(2)}
                      {toTWD(estimateCost.data.max_estimate?.cost) && (
                        <span className="ml-1 text-xs font-normal text-muted-foreground">
                          ({toTWD(estimateCost.data.max_estimate?.cost)})
                        </span>
                      )}
                    </span>
                  </div>

                  {/* Exchange rate info */}
                  {exchangeRate && (
                    <div className="mt-2 flex items-center justify-end gap-1 text-[11px] text-muted-foreground">
                      <span>
                        匯率 1 USD = {exchangeRate.rate.toFixed(2)} TWD
                      </span>
                      <span>·</span>
                      <span>
                        更新：{exchangeRate.source_date}
                      </span>
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
          disabled={!canStart || startOptimization.isPending}
        >
          {startOptimization.isPending && (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          )}
          開始優化
        </Button>
      </div>
    </div>
  );
}
