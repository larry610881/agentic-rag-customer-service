import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { History, Eye, RotateCcw, Loader2, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ROUTES } from "@/routes/paths";
import {
  useOptimizationRuns,
  useRollbackRun,
} from "@/hooks/queries/use-prompt-optimizer";

const STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  running: "執行中",
  failed: "失敗",
  pending: "等待中",
  stopped: "已停止",
};

export default function AdminPromptOptimizerRunsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useOptimizationRuns(page, 20);
  const rollbackMutation = useRollbackRun();

  const runs = data?.items ?? [];
  const totalPages = data ? Math.ceil(data.total / 20) : 1;

  const handleRollback = (runId: string) => {
    rollbackMutation.mutate(runId, {
      onSuccess: () => toast.success("已回滾至優化前狀態"),
      onError: () => toast.error("回滾失敗"),
    });
  };

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed":
        return "default" as const;
      case "running":
        return "secondary" as const;
      case "failed":
        return "destructive" as const;
      default:
        return "outline" as const;
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("zh-TW", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
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
          <History className="h-6 w-6" />
          優化歷史紀錄
        </h1>
        <p className="mt-1 text-muted-foreground">
          查看過往優化紀錄、比較結果與回滾
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          尚無優化紀錄
        </p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>類型</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead>迭代次數</TableHead>
                <TableHead>最佳分數</TableHead>
                <TableHead>建立時間</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => (
                <TableRow key={run.id || run.run_id}>
                  <TableCell>
                    <Badge variant={run.run_type === "validation" ? "secondary" : "outline"}>
                      {run.run_type === "validation" ? "驗收" : "優化"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(run.status)}>
                      {STATUS_LABELS[run.status] || run.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {run.run_type === "validation"
                      ? `${run.current_iteration || 1} 次重複`
                      : `${run.current_iteration} / ${run.max_iterations}`}
                  </TableCell>
                  <TableCell>
                    {run.best_score != null
                      ? run.best_score.toFixed(3)
                      : "—"}
                  </TableCell>
                  <TableCell>{formatDate(run.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          navigate(
                            ROUTES.ADMIN_PROMPT_OPTIMIZER_RUN_DETAIL.replace(
                              ":runId",
                              run.id,
                            ),
                          )
                        }
                      >
                        <Eye className="mr-1 h-4 w-4" />
                        詳情
                      </Button>
                      {run.status === "completed" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRollback(run.id)}
                          disabled={rollbackMutation.isPending}
                        >
                          {rollbackMutation.isPending ? (
                            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                          ) : (
                            <RotateCcw className="mr-1 h-4 w-4" />
                          )}
                          回滾
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                上一頁
              </Button>
              <span className="text-sm text-muted-foreground">
                第 {page} / {totalPages} 頁
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                下一頁
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
