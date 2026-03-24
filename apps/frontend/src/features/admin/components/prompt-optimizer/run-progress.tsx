import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { API_BASE } from "@/lib/api-config";

interface RunProgressProps {
  runId: string;
  onComplete?: () => void;
}

interface ProgressState {
  currentIteration: number;
  maxIterations: number;
  currentScore: number;
  bestScore: number;
  status: string;
}

export function RunProgress({ runId, onComplete }: RunProgressProps) {
  const [progress, setProgress] = useState<ProgressState>({
    currentIteration: 0,
    maxIterations: 1,
    currentScore: 0,
    bestScore: 0,
    status: "connecting",
  });
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef(Date.now());
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const es = new EventSource(
      `${API_BASE}/api/prompt-optimizer/runs/${runId}/progress`,
    );
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress({
        currentIteration: data.current_iteration ?? 0,
        maxIterations: data.max_iterations ?? 1,
        currentScore: data.current_score ?? 0,
        bestScore: data.best_score ?? 0,
        status: data.status ?? "running",
      });

      if (data.status === "completed" || data.status === "failed") {
        es.close();
        onComplete?.();
      }
    };

    es.onerror = () => {
      setProgress((prev) => ({ ...prev, status: "error" }));
      es.close();
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [runId, onComplete]);

  const percent =
    progress.maxIterations > 0
      ? Math.round((progress.currentIteration / progress.maxIterations) * 100)
      : 0;

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = `${minutes}:${String(seconds).padStart(2, "0")}`;

  const statusVariant =
    progress.status === "completed"
      ? "default"
      : progress.status === "failed" || progress.status === "error"
        ? "destructive"
        : "secondary";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Optimization Progress</CardTitle>
        <Badge variant={statusVariant}>{progress.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <Progress value={percent} />
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Iteration {progress.currentIteration} / {progress.maxIterations}
          </span>
          <span>Elapsed: {elapsedStr}</span>
        </div>
        <div className="flex gap-6 text-sm">
          <div>
            <span className="text-muted-foreground">Current Score: </span>
            <span className="font-medium">{progress.currentScore.toFixed(3)}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Best Score: </span>
            <span className="font-medium text-green-400">
              {progress.bestScore.toFixed(3)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
