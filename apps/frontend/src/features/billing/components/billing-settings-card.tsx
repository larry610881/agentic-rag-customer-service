import { useEffect, useState } from "react";
import { Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  useBillingSettings,
  useUpdateBillingSettings,
} from "@/hooks/queries/use-billing-settings";
import {
  describeBillingApiError,
  formatUsdPerPoint,
} from "@/features/billing/billing-labels";
import { formatDate } from "@/lib/format-date";

/** Issue #74 — 平台匯率（1 點 = X USD），方案管理頁頂部卡片 */
export function BillingSettingsCard() {
  const { data, isLoading, isError } = useBillingSettings();
  const update = useUpdateBillingSettings();
  const [rate, setRate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  // usd_per_point 為 Decimal，後端可能序列化成字串
  const current = data ? Number(data.usd_per_point) : null;

  useEffect(() => {
    if (current !== null) setRate(String(current));
  }, [current]);

  const parsed = Number(rate);
  const valid = rate.trim() !== "" && Number.isFinite(parsed) && parsed > 0;
  const dirty = current !== null ? parsed !== current : rate.trim() !== "";

  const handleSave = async () => {
    setError(null);
    if (!valid) {
      setError("匯率必須是大於 0 的數字");
      return;
    }
    try {
      await update.mutateAsync({ usd_per_point: parsed });
    } catch (e) {
      setError(describeBillingApiError(e));
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Coins className="h-4 w-4" />
          計價設定
        </CardTitle>
        <CardDescription>
          點數制方案的平台匯率：模型定價未指定每千 token 點數時，以 USD 成本 ÷ 匯率換算再無條件進位。
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isError ? (
          <p className="text-sm text-destructive">載入匯率失敗</p>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="usd-per-point">每點 USD（usd_per_point）</Label>
              <Input
                id="usd-per-point"
                type="number"
                step="0.000001"
                min="0"
                className="w-48"
                value={rate}
                disabled={isLoading}
                onChange={(e) => setRate(e.target.value)}
              />
            </div>
            <Button
              onClick={handleSave}
              disabled={update.isPending || isLoading || !dirty || !valid}
            >
              {update.isPending ? "儲存中..." : "儲存匯率"}
            </Button>
            <div className="text-xs text-muted-foreground">
              <div>目前：{formatUsdPerPoint(current)}</div>
              {data?.updated_at && (
                <div>
                  更新於 {formatDate(data.updated_at)}
                  {data.updated_by ? `（${data.updated_by}）` : ""}
                </div>
              )}
            </div>
          </div>
        )}
        {error && (
          <p className="mt-2 rounded bg-destructive/10 p-2 text-sm text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
