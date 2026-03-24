import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Copy,
  FileText,
  Loader2,
  Square,
  Upload,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { ROUTES } from "@/routes/paths";
import {
  useOptimizationRunPolling,
  useRollbackRun,
  useStopOptimization,
} from "@/hooks/queries/use-prompt-optimizer";
import { ScoreChart } from "@/features/admin/components/prompt-optimizer/score-chart";
import { PromptDiff } from "@/features/admin/components/prompt-optimizer/prompt-diff";
import { CaseResultsTable } from "@/features/admin/components/prompt-optimizer/case-results-table";
import type { CaseResultData } from "@/features/admin/components/prompt-optimizer/case-results-table";

const STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  running: "執行中",
  failed: "失敗",
  pending: "等待中",
  stopped: "已停止",
  unknown: "未知",
};

const STOPPED_REASON_LABELS: Record<string, string> = {
  user_stopped: "使用者手動停止，已保留最佳結果",
  patience: "連續多輪未改善，提前停止",
  budget: "API 呼叫預算已用盡",
  max_iterations: "已達最大迭代次數",
  converged: "已達滿分，提前完成",
  dry_run: "試跑模式，僅評估基線",
};

const isFinishedStatus = (s: string) =>
  s === "completed" || s === "failed" || s === "stopped";

interface IterationData {
  iteration: number;
  score: number;
  passed_count: number;
  total_count: number;
  is_best: boolean;
  details: Record<string, unknown> | null;
  prompt_snapshot: string;
  created_at: string;
}

export default function AdminPromptOptimizerRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const { data: run } = useOptimizationRunPolling(runId ?? "");
  const stopMutation = useStopOptimization();
  const applyMutation = useRollbackRun();

  const [elapsed, setElapsed] = useState(0);
  const [expandedIter, setExpandedIter] = useState<number | null>(null);
  const startTimeRef = useRef(Date.now());

  const status = run?.status ?? "unknown";
  const currentIteration = run?.current_iteration ?? 0;
  const maxIterations = run?.max_iterations ?? 1;
  const bestScore = run?.best_score ?? 0;
  const baselineScore = run?.baseline_score ?? 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const iterations: IterationData[] = (run as any)?.iterations ?? [];

  const isRunning = status === "running";
  const isFinished = isFinishedStatus(status);

  // Elapsed timer
  useEffect(() => {
    if (isFinished) return;
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [isFinished]);

  // Build score history from iterations (DB) or score_log (in-memory during run)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const scoreLog: { iteration: number; score: number }[] = (run as any)?.score_log ?? [];

  const scoreHistory = useMemo(() => {
    // Prefer iterations from DB (includes during run now, since we save immediately)
    // Fall back to score_log from ActiveRun (in-memory)
    const source = iterations.length > 0
      ? iterations.map((it) => ({ iteration: it.iteration, score: it.score }))
      : scoreLog;
    let runningBest = 0;
    return source.map((p) => {
      if (p.score > runningBest) runningBest = p.score;
      return { iteration: p.iteration, score: p.score, bestScore: runningBest };
    });
  }, [iterations, scoreLog]);

  // Progress log from backend (complete history, no polling gaps)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const progressLog: string[] = (run as any)?.progress_log ?? [];

  const handleStop = useCallback(() => {
    if (!runId) return;
    stopMutation.mutate(runId, {
      onSuccess: () => toast.success("已停止優化，保留最佳結果"),
      onError: () => toast.error("停止優化失敗"),
    });
  }, [runId, stopMutation]);

  const handleCopyPrompt = useCallback((prompt: string) => {
    navigator.clipboard.writeText(prompt).then(
      () => toast.success("已複製提示詞到剪貼簿"),
      () => toast.error("複製失敗"),
    );
  }, []);

  const handleApplyPrompt = useCallback((iteration: number) => {
    if (!runId) return;
    applyMutation.mutate({ runId, iteration }, {
      onSuccess: () => toast.success("已套用提示詞到機器人"),
      onError: () => toast.error("套用失敗"),
    });
  }, [runId, applyMutation]);

  const percent =
    maxIterations > 0 ? Math.round((currentIteration / maxIterations) * 100) : 0;
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = `${minutes}:${String(seconds).padStart(2, "0")}`;

  const statusVariant =
    status === "completed"
      ? "default"
      : status === "failed"
        ? "destructive"
        : "secondary";

  const baselinePrompt = iterations.find((it) => it.iteration === 0)?.prompt_snapshot ?? "";

  // Find the source prompt (best prompt) that was mutated from for a given iteration
  const findSourceIteration = (currentIter: number): IterationData | null => {
    for (let i = iterations.length - 1; i >= 0; i--) {
      const it = iterations[i];
      if (it.iteration >= currentIter) continue;
      if (it.iteration === 0 || it.details?.accepted !== false) {
        return it;
      }
    }
    return iterations[0] ?? null;
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Button
            variant="ghost"
            size="sm"
            className="mb-2"
            onClick={() => navigate(ROUTES.ADMIN_PROMPT_OPTIMIZER_RUNS)}
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回歷史紀錄
          </Button>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Activity className="h-6 w-6" />
            執行詳情
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">Run ID: {runId}</p>
        </div>
        <div className="flex gap-2">
          {isRunning && (
            <Button
              variant="destructive"
              onClick={handleStop}
              disabled={stopMutation.isPending}
            >
              {stopMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Square className="mr-2 h-4 w-4" />
              )}
              停止並保留最佳結果
            </Button>
          )}
          {isFinished && (
            <Button
              variant="outline"
              onClick={() => navigate(ROUTES.ADMIN_PROMPT_OPTIMIZER_RUNS)}
            >
              <FileText className="mr-2 h-4 w-4" />
              返回列表
            </Button>
          )}
        </div>
      </div>

      {/* Progress */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">執行進度</CardTitle>
          <Badge variant={statusVariant}>{STATUS_LABELS[status] || status}</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <Progress value={percent} />
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>第 {currentIteration} / {maxIterations} 輪</span>
            <span>已用時間：{elapsedStr}</span>
          </div>
          <div className="flex gap-6 text-sm">
            <div>
              <span className="text-muted-foreground">基線分數：</span>
              <span className="font-medium">{baselineScore > 0 ? baselineScore.toFixed(3) : "—"}</span>
            </div>
            <div>
              <span className="text-muted-foreground">最佳分數：</span>
              <span className="font-medium text-green-600">{bestScore > 0 ? bestScore.toFixed(3) : "—"}</span>
            </div>
          </div>
          {isRunning && run?.progress_message && (
            <div className="flex items-center gap-2 rounded border bg-muted/30 p-2 text-sm">
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
              <span>{run.progress_message}</span>
            </div>
          )}
          {run?.stopped_reason && (
            <div className="rounded border border-yellow-200 bg-yellow-50 p-2 text-sm text-yellow-700">
              {STOPPED_REASON_LABELS[run.stopped_reason] ?? run.stopped_reason}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Execution log (during running) */}
      {progressLog.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">執行紀錄</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5 text-sm">
              {progressLog.map((msg, i) => (
                <div key={i} className="flex items-center gap-2">
                  {msg.includes("✓") ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                  ) : msg.includes("✗") ? (
                    <XCircle className="h-4 w-4 shrink-0 text-red-400" />
                  ) : (
                    <Activity className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <span className={msg.includes("✓") ? "text-green-700" : msg.includes("✗") ? "text-muted-foreground" : ""}>
                    {msg}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Score chart */}
      {scoreHistory.length > 0 && <ScoreChart data={scoreHistory} />}

      {/* Iteration prompt diffs (only when iterations loaded from DB) */}
      {iterations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">提示詞變更紀錄</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {iterations.map((it) => {
              const accepted = it.details?.accepted !== false;
              const isExpanded = expandedIter === it.iteration;

              return (
                <div key={it.iteration} className="rounded border">
                  {/* Row header */}
                  <button
                    className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted/50 transition-colors"
                    onClick={() => setExpandedIter(isExpanded ? null : it.iteration)}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <Badge variant="outline" className="shrink-0">
                      第 {it.iteration} 輪
                    </Badge>
                    <span className="font-medium">{it.score.toFixed(4)}</span>
                    <span className="text-muted-foreground">
                      ({it.passed_count}/{it.total_count} 通過)
                    </span>
                    {it.is_best && (
                      <Badge variant="default" className="shrink-0">最佳</Badge>
                    )}
                    {it.iteration > 0 && (
                      <Badge
                        variant={accepted ? "outline" : "secondary"}
                        className={accepted ? "border-green-500 text-green-600" : ""}
                      >
                        {accepted ? "接受" : "放棄"}
                      </Badge>
                    )}
                  </button>

                  {/* Expanded: show prompt diff + case results */}
                  {isExpanded && (
                    <div className="border-t px-3 py-3">
                      {it.iteration === 0 ? (
                        <div>
                          <p className="mb-2 text-xs font-medium text-muted-foreground">
                            基線提示詞（原始）
                          </p>
                          <pre className="max-h-[400px] overflow-auto whitespace-pre-wrap rounded bg-muted/30 p-3 text-xs">
                            {it.prompt_snapshot || "(空)"}
                          </pre>
                        </div>
                      ) : (() => {
                        const source = findSourceIteration(it.iteration);
                        const sourcePrompt = source?.prompt_snapshot ?? baselinePrompt;
                        const sourceLabel = !source || source.iteration === 0
                          ? "基線"
                          : `最佳 (第 ${source.iteration} 輪)`;
                        return sourcePrompt ? (
                          <PromptDiff
                            before={sourcePrompt}
                            after={it.prompt_snapshot}
                            title={`第 ${it.iteration} 輪 vs ${sourceLabel}`}
                          />
                        ) : (
                          <pre className="max-h-[400px] overflow-auto whitespace-pre-wrap rounded bg-muted/30 p-3 text-xs">
                            {it.prompt_snapshot || "(空)"}
                          </pre>
                        );
                      })()}

                      {/* Action buttons: copy + apply */}
                      {it.prompt_snapshot && isFinished && (
                        <div className="mt-3 flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleCopyPrompt(it.prompt_snapshot)}
                          >
                            <Copy className="mr-1.5 h-3.5 w-3.5" />
                            複製提示詞
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="default"
                                size="sm"
                                disabled={applyMutation.isPending}
                              >
                                {applyMutation.isPending ? (
                                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Upload className="mr-1.5 h-3.5 w-3.5" />
                                )}
                                套用到機器人
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>確認套用提示詞</AlertDialogTitle>
                                <AlertDialogDescription>
                                  將第 {it.iteration} 輪的提示詞（分數：{it.score.toFixed(4)}）寫入機器人的 prompt 欄位。此操作會覆蓋目前的提示詞，確定要繼續嗎？
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>取消</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => handleApplyPrompt(it.iteration)}
                                >
                                  確認套用
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      )}

                      {/* Per-case test results */}
                      <CaseResultsTable
                        caseResults={it.details?.case_results as CaseResultData[] | undefined}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
