import { useState } from "react";
import { Plus, RotateCcw, Power } from "lucide-react";
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
import {
  useDeactivatePricing,
  useListPricing,
} from "@/hooks/queries/use-pricing";
import { PricingCreateDialog } from "@/features/admin/components/pricing-create-dialog";
import { PricingRecalcWizard } from "@/features/admin/components/pricing-recalc-wizard";
import { PricingHistoryTable } from "@/features/admin/components/pricing-history-table";
import type { ModelPricing } from "@/types/pricing";

function isCurrentlyActive(p: ModelPricing): boolean {
  const now = Date.now();
  const from = new Date(p.effective_from).getTime();
  const to = p.effective_to ? new Date(p.effective_to).getTime() : null;
  return from <= now && (to === null || to > now);
}

function formatPrice(n: number): string {
  if (n === 0) return "—";
  return `$${n.toFixed(n < 0.1 ? 4 : 2)}`;
}

export default function AdminPricingPage() {
  const { data: pricings, isLoading } = useListPricing();
  const deactivate = useDeactivatePricing();
  const [createOpen, setCreateOpen] = useState(false);
  const [recalcOpen, setRecalcOpen] = useState(false);

  const handleDeactivate = async (p: ModelPricing) => {
    if (
      !window.confirm(
        `停用「${p.provider}/${p.model_id}」?\n` +
          `停用後新的 usage 會 fallback 到 DEFAULT_MODELS（hardcoded）。` +
          `歷史 usage 不受影響。`,
      )
    )
      return;
    try {
      await deactivate.mutateAsync(p.id);
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "停用失敗");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">LLM 定價管理</h1>
          <p className="text-muted-foreground">
            新增 / 停用 model pricing 版本。改價一律產生新版本，歷史 snapshot 不變。
            回溯重算走獨立路徑並留 audit。
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setRecalcOpen(true)}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            回溯重算
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            新增版本
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">載入中...</p>
      ) : !pricings || pricings.length === 0 ? (
        <p className="text-muted-foreground">
          尚無 pricing 版本 — 系統將 fallback 到 DEFAULT_MODELS
        </p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Input</TableHead>
                <TableHead>Output</TableHead>
                <TableHead>Cache R / W</TableHead>
                <TableHead>Effective</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead>Note</TableHead>
                <TableHead className="w-[100px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pricings.map((p) => {
                const active = isCurrentlyActive(p);
                return (
                  <TableRow key={p.id}>
                    <TableCell>{p.provider}</TableCell>
                    <TableCell className="font-mono text-sm">
                      {p.model_id}
                    </TableCell>
                    <TableCell>{formatPrice(p.input_price)}</TableCell>
                    <TableCell>{formatPrice(p.output_price)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatPrice(p.cache_read_price)} /{" "}
                      {formatPrice(p.cache_creation_price)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {new Date(p.effective_from).toLocaleString()}
                      {p.effective_to && (
                        <>
                          <br />→{" "}
                          {new Date(p.effective_to).toLocaleString()}
                        </>
                      )}
                    </TableCell>
                    <TableCell>
                      {active ? (
                        <Badge variant="default">生效中</Badge>
                      ) : p.effective_to ? (
                        <Badge variant="secondary">已停用</Badge>
                      ) : (
                        <Badge variant="outline">排程中</Badge>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-xs">
                      {p.note ?? "—"}
                    </TableCell>
                    <TableCell>
                      {active && (
                        <Button
                          variant="ghost"
                          size="icon"
                          title="停用此版本"
                          onClick={() => handleDeactivate(p)}
                        >
                          <Power className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <section className="space-y-2 pt-6">
        <h2 className="text-xl font-semibold">回溯重算歷史</h2>
        <PricingHistoryTable />
      </section>

      <PricingCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
      <PricingRecalcWizard
        open={recalcOpen}
        onOpenChange={setRecalcOpen}
      />
    </div>
  );
}
