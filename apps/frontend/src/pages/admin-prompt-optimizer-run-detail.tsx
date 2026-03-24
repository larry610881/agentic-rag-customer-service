import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Activity, ArrowLeft, Loader2, Square, FileText } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ROUTES } from "@/routes/paths";
import { API_BASE } from "@/lib/api-config";
import {
  useOptimizationRun,
  useStopOptimization,
} from "@/hooks/queries/use-prompt-optimizer";
import { ScoreChart } from "@/features/admin/components/prompt-optimizer/score-chart";
import { PromptDiff } from "@/features/admin/components/prompt-optimizer/prompt-diff";

const STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  running: "執行中",
  failed: "失敗",
  pending: "等待中",
  stopped: "已停止",
  connecting: "連線中",
  unknown: "未知",
};

interface SSEProgress {
  current_iteration: number;
  max_iterations: number;
  current_score: number;
  best_score: number;
  status: string;
  diff?: { before: string; after: string };
}

export default function AdminPromptOptimizerRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const { data: run } = useOptimizationRun(runId ?? "");
  const stopMutation = useStopOptimization();

  const [progress, setProgress] = useState<SSEProgress | null>(null);
  const [scoreHistory, setScoreHistory] = useState<
    { iteration: number; score: number; bestScore: number }[]
  >([]);
  const [elapsed, setElapsed] = useState(0);
  const [diffData, setDiffData] = useState<{
    before: string;
    after: string;
  } | null>(null);

  const startTimeRef = useRef(Date.now());
  const eventSourceRef = useRef<EventSource | null>(null);

  // Elapsed timer
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // SSE connection
  useEffect(() => {
    if (!runId) return;

    const es = new EventSource(
      `${API_BASE}/api/v1/prompt-optimizer/runs/${runId}/progress`,
    );
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      const data: SSEProgress = JSON.parse(event.data);
      setProgress(data);

      if (data.current_iteration > 0) {
        setScoreHistory((prev) => {
          const exists = prev.some(
            (p) => p.iteration === data.current_iteration,
          );
          if (exists) return prev;
          return [
            ...prev,
            {
              iteration: data.current_iteration,
              score: data.current_score,
              bestScore: data.best_score,
            },
          ];
        });
      }

      if (data.diff) {
        setDiffData(data.diff);
      }

      if (data.status === "completed" || data.status === "failed") {
        es.close();
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [runId]);

  const handleStop = useCallback(() => {
    if (!runId) return;
    stopMutation.mutate(runId, {
      onSuccess: () => {
        toast.success("已停止優化，保留最佳結果");
        eventSourceRef.current?.close();
      },
      onError: () => toast.error("停止優化失敗"),
    });
  }, [runId, stopMutation]);

  const currentIteration = progress?.current_iteration ?? run?.current_iteration ?? 0;
  const maxIterations = progress?.max_iterations ?? run?.max_iterations ?? 1;
  const currentScore = progress?.current_score ?? 0;
  const bestScore = progress?.best_score ?? run?.best_score ?? 0;
  const status = progress?.status ?? run?.status ?? "unknown";

  const percent =
    maxIterations > 0 ? Math.round((currentIteration / maxIterations) * 100) : 0;

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = `${minutes}:${String(seconds).padStart(2, "0")}`;

  const isRunning = status === "running" || status === "connecting";
  const isFinished = status === "completed" || status === "failed" || status === "stopped";

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
              onClick={() =>
                navigate(ROUTES.ADMIN_PROMPT_OPTIMIZER_RUNS)
              }
            >
              <FileText className="mr-2 h-4 w-4" />
              查看報告
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
              <span className="text-muted-foreground">當前分數：</span>
              <span className="font-medium">{currentScore.toFixed(3)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">最佳分數：</span>
              <span className="font-medium text-green-400">
                {bestScore.toFixed(3)}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Score chart */}
      <ScoreChart data={scoreHistory} />

      {/* Prompt diff */}
      {diffData && (
        <PromptDiff
          before={diffData.before}
          after={diffData.after}
          title="最新 Prompt 變更"
        />
      )}
    </div>
  );
}
