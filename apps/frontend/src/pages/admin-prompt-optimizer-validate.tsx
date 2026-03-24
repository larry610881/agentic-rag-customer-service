import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  useEvalDatasets,
  useRunValidation,
  useEstimateCost,
  useExchangeRate,
} from "@/hooks/queries/use-prompt-optimizer";
import type {
  ValidationResult,
  ValidationCaseResult,
} from "@/hooks/queries/use-prompt-optimizer";
import { useBots } from "@/hooks/queries/use-bots";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import {
  ArrowLeft,
  Calculator,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
} from "lucide-react";
import { ROUTES } from "@/routes/paths";

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
  const [datasetId, setDatasetId] = useState("");
  const [botId, setBotId] = useState("");
  const [repeats, setRepeats] = useState(5);
  const { data: datasets } = useEvalDatasets(1, 50);
  const { data: botsData } = useBots(1, 100);
  const bots = botsData?.items ?? [];
  const validation = useRunValidation();
  const estimateCost = useEstimateCost();
  const { data: exchangeRate } = useExchangeRate("twd");
  const result = validation.data as ValidationResult | undefined;

  // Auto-select bot when dataset changes
  const selectedDataset = datasets?.items?.find((d) => d.id === datasetId);
  useEffect(() => {
    if (selectedDataset?.bot_id) {
      setBotId(selectedDataset.bot_id);
    }
  }, [selectedDataset?.bot_id]);

  // Auto-estimate cost when dataset + bot selected
  useEffect(() => {
    if (datasetId && botId) {
      const selectedBot = bots.find((b) => b.id === botId);
      estimateCost.mutate({
        dataset_id: datasetId,
        bot_id: botId,
        model_id: selectedBot?.llm_model || "",
        max_iterations: 0,
        patience: 0,
        budget: 0,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, botId]);

  const handleRun = () => {
    if (!datasetId) return;
    validation.mutate({ dataset_id: datasetId, bot_id: botId, repeats });
  };

  // Cost calculation
  const evalCostPerCall = estimateCost.data?.eval_cost_per_call ?? 0;
  const numCases = selectedDataset?.test_case_count ?? 0;
  const totalCalls = repeats * numCases;
  const totalCostUsd = totalCalls * evalCostPerCall;
  const twdRate = exchangeRate?.rate ?? 32;
  const totalCostTwd = totalCostUsd * twdRate;

  return (
    <div className="space-y-6">
      {/* Header + Back */}
      <div className="flex items-center gap-3">
        <Link to={ROUTES.ADMIN_PROMPT_OPTIMIZER}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">驗收評估</h1>
          <p className="text-muted-foreground">
            對 prompt 重複執行 N 次評估，統計 pass rate 判定穩定性
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">測試集</label>
          <Select value={datasetId} onValueChange={setDatasetId}>
            <SelectTrigger className="w-[360px]">
              <SelectValue placeholder="選擇測試集..." />
            </SelectTrigger>
            <SelectContent>
              {datasets?.items?.map((ds) => (
                <SelectItem key={ds.id} value={ds.id}>
                  {ds.name} ({ds.test_case_count} cases)
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Bot</label>
          <Select value={botId} onValueChange={setBotId}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="選擇 Bot..." />
            </SelectTrigger>
            <SelectContent>
              {bots.map((bot) => (
                <SelectItem key={bot.id} value={bot.id}>
                  {bot.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">重複次數</label>
          <Select
            value={String(repeats)}
            onValueChange={(v) => setRepeats(Number(v))}
          >
            <SelectTrigger className="w-[100px]">
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
        </div>

        <Button
          onClick={handleRun}
          disabled={!datasetId || validation.isPending}
        >
          {validation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              評估中...
            </>
          ) : (
            "開始驗收"
          )}
        </Button>
      </div>

      {/* Cost Estimate */}
      {datasetId && numCases > 0 && (
        <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm">
          <Calculator className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">預估成本：</span>
          <span className="font-medium">
            {totalCalls} 次 API 呼叫
          </span>
          <span className="text-muted-foreground">
            ({repeats} 重複 × {numCases} cases)
          </span>
          {evalCostPerCall > 0 && (
            <>
              <span className="text-muted-foreground ml-2">≈</span>
              <span className="font-medium">
                ${totalCostUsd.toFixed(4)} USD
              </span>
              <span className="text-muted-foreground">
                (≈ NT${totalCostTwd.toFixed(1)})
              </span>
            </>
          )}
        </div>
      )}

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
              <p className="font-semibold text-red-700 mb-1">
                P0 安全案例失敗
              </p>
              {result.p0_failures.map((cid) => {
                const cr = result.case_results.find(
                  (c) => c.case_id === cid,
                );
                return (
                  <p key={cid} className="text-sm text-red-600">
                    {cid} — pass rate{" "}
                    {cr ? `${Math.round(cr.pass_rate * 100)}%` : "N/A"} (需
                    100%)
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
                {result.unstable_cases} 個案例通過但不穩定（pass rate &lt;
                100%），建議觀察
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
                    <Badge
                      variant={
                        cr.priority === "P0" ? "destructive" : "outline"
                      }
                    >
                      {cr.priority}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {cr.case_id}
                  </TableCell>
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
