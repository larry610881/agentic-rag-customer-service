import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useDryRunRecalculate,
  useExecuteRecalculate,
  useListPricing,
} from "@/hooks/queries/use-pricing";
import type { DryRunRecalcResult } from "@/types/pricing";

interface PricingRecalcWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function toIsoUtc(local: string): string {
  return new Date(local).toISOString();
}

function defaultLocalInput(offsetMinutes: number): string {
  const d = new Date(Date.now() + offsetMinutes * 60_000);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

type WizardStep = "select" | "preview" | "confirm" | "done";

export function PricingRecalcWizard({
  open,
  onOpenChange,
}: PricingRecalcWizardProps) {
  const [step, setStep] = useState<WizardStep>("select");
  const [pricingId, setPricingId] = useState("");
  const [from, setFrom] = useState(defaultLocalInput(-60)); // 1hr ago
  const [to, setTo] = useState(defaultLocalInput(0));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<DryRunRecalcResult | null>(null);

  const { data: pricings } = useListPricing();
  const dryRun = useDryRunRecalculate();
  const execute = useExecuteRecalculate();

  const resetAll = () => {
    setStep("select");
    setPricingId("");
    setReason("");
    setPreview(null);
    setError(null);
  };

  const handleClose = (next: boolean) => {
    if (!next) resetAll();
    onOpenChange(next);
  };

  const handleDryRun = async () => {
    setError(null);
    if (!pricingId) {
      setError("請選擇目標 pricing");
      return;
    }
    try {
      const result = await dryRun.mutateAsync({
        pricing_id: pricingId,
        recalc_from: toIsoUtc(from),
        recalc_to: toIsoUtc(to),
      });
      setPreview(result);
      setStep("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "dry-run 失敗");
    }
  };

  const handleExecute = async () => {
    setError(null);
    if (!preview) return;
    if (!reason.trim()) {
      setError("必須輸入重算理由");
      return;
    }
    try {
      await execute.mutateAsync({
        dry_run_token: preview.dry_run_token,
        reason,
      });
      setStep("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "執行失敗");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>回溯重算 estimated_cost</DialogTitle>
        </DialogHeader>

        {step === "select" && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="pricing">目標 Pricing 版本</Label>
              <select
                id="pricing"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={pricingId}
                onChange={(e) => setPricingId(e.target.value)}
              >
                <option value="">-- 選擇 --</option>
                {(pricings ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.provider} / {p.model_id} (effective{" "}
                    {new Date(p.effective_from).toLocaleString()})
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="from">重算起 (inclusive)</Label>
                <Input
                  id="from"
                  type="datetime-local"
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="to">重算迄 (exclusive)</Label>
                <Input
                  id="to"
                  type="datetime-local"
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button variant="outline" onClick={() => handleClose(false)}>
                取消
              </Button>
              <Button
                onClick={handleDryRun}
                disabled={dryRun.isPending}
              >
                {dryRun.isPending ? "計算中..." : "預覽影響"}
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === "preview" && preview && (
          <div className="space-y-4">
            <div className="rounded-md border bg-muted/40 p-4 space-y-2">
              <div className="text-sm text-muted-foreground">
                以下為區間內符合條件的 usage rows 重算預覽（尚未寫入）
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>影響筆數：</div>
                <div className="font-mono">{preview.affected_rows}</div>
                <div>原成本總和：</div>
                <div className="font-mono">
                  ${preview.cost_before_total.toFixed(6)}
                </div>
                <div>新成本總和：</div>
                <div className="font-mono">
                  ${preview.cost_after_total.toFixed(6)}
                </div>
                <div>差異：</div>
                <div
                  className={`font-mono ${
                    preview.cost_delta >= 0
                      ? "text-amber-600"
                      : "text-emerald-600"
                  }`}
                >
                  {preview.cost_delta >= 0 ? "+" : ""}$
                  {preview.cost_delta.toFixed(6)}
                </div>
              </div>
            </div>
            <div>
              <Label htmlFor="reason">重算理由（必填，寫入 audit log）</Label>
              <Textarea
                id="reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="OpenAI 6/15 官方調價，補算 6/13~6/14 漏期"
                rows={3}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("select")}>
                回上一步
              </Button>
              <Button
                variant="destructive"
                onClick={handleExecute}
                disabled={execute.isPending}
              >
                {execute.isPending ? "執行中..." : "確認執行"}
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === "done" && (
          <div className="space-y-4">
            <div className="rounded-md border bg-emerald-50 p-4 text-sm text-emerald-900">
              ✅ 回溯重算完成，已寫入 audit log。歷史紀錄可在下方表格查看。
            </div>
            <DialogFooter>
              <Button onClick={() => handleClose(false)}>關閉</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
