import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Activity, ArrowLeft, Loader2, Square, FileText } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ROUTES } from "@/routes/paths";
import {
  useOptimizationRunPolling,
  useStopOptimization,
} from "@/hooks/queries/use-prompt-optimizer";
import { ScoreChart } from "@/features/admin/components/prompt-optimizer/score-chart";

const STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  running: "執行中",
  failed: "失敗",
  pending: "等待中",
  stopped: "已停止",
  unknown: "未知",
};

const isFinishedStatus = (s: string) =>
  s === "completed" || s === "failed" || s === "stopped";

export default function AdminPromptOptimizerRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const { data: run } = useOptimizationRunPolling(runId ?? "");
  const stopMutation = useStopOptimization();

  const [scoreHistory, setScoreHistory] = useState<
    { iteration: number; score: number; bestScore: number }[]
  >([]);
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef(Date.now());

  const status = run?.status ?? "unknown";
  const currentIteration = run?.current_iteration ?? 0;
  const maxIterations = run?.max_iterations ?? 1;
  const bestScore = run?.best_score ?? 0;
  const baselineScore = run?.baseline_score ?? 0;

  const isRunning = status === "running";
  const isFinished = isFinishedStatus(status);

  // Elapsed timer — stop when finished
  useEffect(() => {
    if (isFinished) return;
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [isFinished]);

  // Build score history from polling data
  useEffect(() => {
    if (!run || currentIteration === 0) return;
    setScoreHistory((prev) => {
      const exists = prev.some((p) => p.iteration === currentIteration);
      if (exists) return prev;
      return [
        ...prev,
        {
          iteration: currentIteration,
          score: bestScore,
          bestScore: bestScore,
        },
      ];
    });
  }, [currentIteration, bestScore, run]);

  const handleStop = useCallback(() => {
    if (!runId) return;
    stopMutation.mutate(runId, {
      onSuccess: () => toast.success("已停止優化，保留最佳結果"),
      onError: () => toast.error("停止優化失敗"),
    });
  }, [runId, stopMutation]);

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
          <p className="mt-1 text-sm text-muted-foreground">
            Run ID: {runId}
          </p>
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

      {/* Progress section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">執行進度</CardTitle>
          <Badge variant={statusVariant}>
            {STATUS_LABELS[status] || status}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <Progress value={percent} />
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              第 {currentIteration} / {maxIterations} 輪
            </span>
            <span>已用時間：{elapsedStr}</span>
          </div>
          <div className="flex gap-6 text-sm">
            <div>
              <span className="text-muted-foreground">基線分數：</span>
              <span className="font-medium">{baselineScore.toFixed(3)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">最佳分數：</span>
              <span className="font-medium text-green-600">
                {bestScore.toFixed(3)}
              </span>
            </div>
          </div>

          {/* Progress message */}
          {isRunning && run?.progress_message && (
            <div className="flex items-center gap-2 rounded border bg-muted/30 p-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span>{run.progress_message}</span>
            </div>
          )}

          {/* Stopped reason */}
          {run?.stopped_reason && (
            <div className="rounded border border-yellow-200 bg-yellow-50 p-2 text-sm text-yellow-700">
              {run.stopped_reason}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Score chart */}
      {scoreHistory.length > 0 && <ScoreChart data={scoreHistory} />}
    </div>
  );
}
