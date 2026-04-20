import { useState } from "react";
import { Plus, Settings, Trash2, CheckCircle2, XCircle } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { usePlans, useDeletePlan } from "@/hooks/queries/use-plans";
import { PlanFormDialog } from "@/features/admin/components/plan-form-dialog";
import type { Plan } from "@/types/plan";

function formatTokens(n: number): string {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)} 億`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(0)} 萬`;
  return n.toLocaleString();
}

export default function AdminPlansPage() {
  const { data: plans, isLoading } = usePlans(true);
  const deleteMutation = useDeletePlan();
  const [editPlan, setEditPlan] = useState<Plan | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  const handleEdit = (p: Plan) => {
    setEditPlan(p);
    setFormOpen(true);
  };

  const handleCreate = () => {
    setEditPlan(null);
    setFormOpen(true);
  };

  const handleSoftDelete = async (p: Plan) => {
    if (!window.confirm(`停用方案「${p.name}」？\n（既有綁定的租戶仍可使用）`)) return;
    try {
      await deleteMutation.mutateAsync({ id: p.id, force: false });
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "停用失敗");
    }
  };

  const handleHardDelete = async (p: Plan) => {
    if (
      !window.confirm(
        `永久刪除方案「${p.name}」？\n` +
          `若有租戶綁定會回 409 錯誤；確定無人綁才能成功。`,
      )
    )
      return;
    try {
      await deleteMutation.mutateAsync({ id: p.id, force: true });
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "刪除失敗");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">方案管理</h1>
          <p className="text-muted-foreground">
            設定月度基礎額度 / 加值包配置 / 價格 — 供租戶綁定使用
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          新增方案
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">載入中...</p>
      ) : !plans || plans.length === 0 ? (
        <p className="text-muted-foreground">尚無方案</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>月基礎額度</TableHead>
                <TableHead>加值包</TableHead>
                <TableHead>月費</TableHead>
                <TableHead>加值價</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead>說明</TableHead>
                <TableHead className="w-[140px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell>{formatTokens(p.base_monthly_tokens)}</TableCell>
                  <TableCell>{formatTokens(p.addon_pack_tokens)}</TableCell>
                  <TableCell>
                    {Number(p.base_price).toLocaleString()} {p.currency}
                  </TableCell>
                  <TableCell>
                    {Number(p.addon_price).toLocaleString()} {p.currency}
                  </TableCell>
                  <TableCell>
                    {p.is_active ? (
                      <Badge variant="default" className="gap-1">
                        <CheckCircle2 className="h-3 w-3" />
                        啟用
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="gap-1">
                        <XCircle className="h-3 w-3" />
                        停用
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                    {p.description ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        title="編輯"
                        onClick={() => handleEdit(p)}
                      >
                        <Settings className="h-4 w-4" />
                      </Button>
                      {p.is_active ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          title="停用 (軟刪)"
                          onClick={() => handleSoftDelete(p)}
                        >
                          <XCircle className="h-4 w-4" />
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="icon"
                          title="永久刪除"
                          onClick={() => handleHardDelete(p)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <PlanFormDialog
        plan={editPlan}
        open={formOpen}
        onOpenChange={setFormOpen}
      />
    </div>
  );
}
