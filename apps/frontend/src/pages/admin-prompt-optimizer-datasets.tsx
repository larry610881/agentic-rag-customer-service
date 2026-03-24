import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Database,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
  useEvalDatasets,
  useDeleteEvalDataset,
} from "@/hooks/queries/use-prompt-optimizer";

export default function AdminPromptOptimizerDatasetsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useEvalDatasets(page, 20);
  const deleteMutation = useDeleteEvalDataset();

  const datasets = data?.items ?? [];
  const totalPages = data ? Math.ceil(data.total / 20) : 1;

  const handleDelete = (id: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => toast.success("情境集已刪除"),
      onError: () => toast.error("刪除失敗"),
    });
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
        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold">
              <Database className="h-6 w-6" />
              情境集管理
            </h1>
            <p className="mt-1 text-muted-foreground">
              建立與管理評估用的測試情境集
            </p>
          </div>
          <Button
            onClick={() => navigate(ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASET_NEW)}
          >
            <Plus className="mr-2 h-4 w-4" />
            新增情境集
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : datasets.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          尚無情境集，點擊「新增情境集」開始建立
        </p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>描述</TableHead>
                <TableHead>案例數</TableHead>
                <TableHead>更新時間</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {datasets.map((ds) => (
                <TableRow key={ds.id}>
                  <TableCell
                    className="cursor-pointer font-medium text-primary hover:underline"
                    onClick={() =>
                      navigate(
                        ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASET_EDIT.replace(
                          ":id",
                          ds.id,
                        ),
                      )
                    }
                  >
                    {ds.name}
                  </TableCell>
                  <TableCell className="max-w-[300px] truncate text-muted-foreground">
                    {ds.description || "—"}
                  </TableCell>
                  <TableCell>{ds.test_case_count}</TableCell>
                  <TableCell>{formatDate(ds.updated_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          navigate(
                            ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASET_EDIT.replace(
                              ":id",
                              ds.id,
                            ),
                          )
                        }
                      >
                        <Pencil className="mr-1 h-4 w-4" />
                        編輯
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDelete(ds.id)}
                        disabled={deleteMutation.isPending}
                      >
                        {deleteMutation.isPending ? (
                          <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="mr-1 h-4 w-4" />
                        )}
                        刪除
                      </Button>
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
