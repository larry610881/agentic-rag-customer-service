import { useEffect, useState } from "react";
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
import { useUpdatePricingPoints } from "@/hooks/queries/use-pricing";
import { describeBillingApiError } from "@/features/billing/billing-labels";
import type { ModelPricing } from "@/types/pricing";

interface PricingPointsDialogProps {
  pricing: ModelPricing | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function toText(v: number | null | undefined): string {
  return v === null || v === undefined ? "" : String(v);
}

/** Issue #74 — 編輯既有 pricing 版本的每千 token 點數（PUT 只動這兩欄） */
export function PricingPointsDialog({
  pricing,
  open,
  onOpenChange,
}: PricingPointsDialogProps) {
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const update = useUpdatePricingPoints();

  useEffect(() => {
    if (open && pricing) {
      setInput(toText(pricing.points_per_1k_input));
      setOutput(toText(pricing.points_per_1k_output));
      setError(null);
    }
  }, [open, pricing]);

  const handleSave = async () => {
    if (!pricing) return;
    setError(null);
    const inBlank = input.trim() === "";
    const outBlank = output.trim() === "";
    if (inBlank !== outBlank) {
      setError("輸入 / 輸出點數需同時填寫，或同時留空（改用平台匯率換算）");
      return;
    }
    const pointsIn = inBlank ? null : Number(input);
    const pointsOut = outBlank ? null : Number(output);
    if (
      (pointsIn !== null && (!Number.isFinite(pointsIn) || pointsIn < 0)) ||
      (pointsOut !== null && (!Number.isFinite(pointsOut) || pointsOut < 0))
    ) {
      setError("每千 token 點數必須是 ≥ 0 的數字");
      return;
    }
    try {
      await update.mutateAsync({
        id: pricing.id,
        data: { points_per_1k_input: pointsIn, points_per_1k_output: pointsOut },
      });
      onOpenChange(false);
    } catch (e) {
      setError(describeBillingApiError(e, "更新失敗"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            編輯點數 — {pricing ? `${pricing.provider}/${pricing.model_id}` : ""}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="edit_points_per_1k_input">每千 token 輸入點數</Label>
              <Input
                id="edit_points_per_1k_input"
                type="number"
                step="0.0001"
                min="0"
                value={input}
                onChange={(e) => setInput(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="edit_points_per_1k_output">每千 token 輸出點數</Label>
              <Input
                id="edit_points_per_1k_output"
                type="number"
                step="0.0001"
                min="0"
                value={output}
                onChange={(e) => setOutput(e.target.value)}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            兩欄同時留空 = 清除點數表，改用平台匯率換算。不影響 USD 定價與歷史 usage。
          </p>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={update.isPending}
          >
            取消
          </Button>
          <Button onClick={handleSave} disabled={update.isPending || !pricing}>
            {update.isPending ? "儲存中..." : "儲存點數"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
