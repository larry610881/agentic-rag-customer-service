import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useUpdateTenantBillingPolicy } from "@/hooks/queries/use-tenant-billing-policy";
import type { TenantQuota } from "@/hooks/queries/use-tenant-quota";
import type { ExhaustionPolicy } from "@/types/billing";
import {
  DEFAULT_BLOCK_MESSAGE,
  EXHAUSTION_POLICY_HINTS,
  describeBillingApiError,
  exhaustionPolicyLabel,
} from "@/features/billing/billing-labels";

interface QuotaPolicyCardProps {
  quota: TenantQuota;
  tenantId: string | null;
}

/**
 * Issue #74 — 租戶額度頁的用盡策略區塊。
 * 方案允許時可切換自動展延 / 用完即擋並編輯被擋文案；否則唯讀並提示「由方案決定」。
 */
export function QuotaPolicyCard({ quota, tenantId }: QuotaPolicyCardProps) {
  // 徽章 / 開關以「生效策略」為準；方案預設用來判斷是否要清除覆寫
  const planDefault: ExhaustionPolicy = quota.exhaustion_policy ?? "auto_topup";
  const effective: ExhaustionPolicy = quota.effective_policy ?? planDefault;
  const mayChange = quota.tenant_may_change_policy === true;
  const gracePercent = Number(quota.grace_percent ?? 0);
  const update = useUpdateTenantBillingPolicy(tenantId);

  const [autoTopup, setAutoTopup] = useState(effective === "auto_topup");
  const [message, setMessage] = useState(quota.block_message ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setAutoTopup(effective === "auto_topup");
    setMessage(quota.block_message ?? "");
  }, [effective, quota.block_message]);

  const nextPolicy: ExhaustionPolicy = autoTopup ? "auto_topup" : "block";
  const dirty =
    nextPolicy !== effective || message.trim() !== (quota.block_message ?? "").trim();

  const handleSave = async () => {
    setError(null);
    setSaved(false);
    try {
      // 回到方案預設 → 送 null 清除覆寫，避免留下與方案相同的覆寫值
      await update.mutateAsync({
        exhaustion_policy: nextPolicy === planDefault ? null : nextPolicy,
        block_message: message.trim() === "" ? null : message.trim(),
      });
      setSaved(true);
    } catch (e) {
      setError(describeBillingApiError(e));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="h-4 w-4" />
          額度用盡策略
          <Badge variant={effective === "block" ? "destructive" : "default"}>
            {exhaustionPolicyLabel(effective)}
          </Badge>
        </CardTitle>
        <CardDescription>
          {EXHAUSTION_POLICY_HINTS[effective]}
          {gracePercent > 0 ? `；寬限 ${gracePercent}%` : ""}
          {effective !== planDefault
            ? `（方案預設：${exhaustionPolicyLabel(planDefault)}）`
            : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {mayChange ? (
          <>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div className="space-y-0.5">
                <Label htmlFor="policy-auto-topup">自動展延</Label>
                <p className="text-xs text-muted-foreground">
                  開啟 = 自動展延；關閉 = 用完即擋
                </p>
              </div>
              <Switch
                id="policy-auto-topup"
                checked={autoTopup}
                onCheckedChange={setAutoTopup}
                disabled={update.isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="policy-block-message">被擋文案</Label>
              <Textarea
                id="policy-block-message"
                rows={2}
                value={message}
                placeholder={DEFAULT_BLOCK_MESSAGE}
                disabled={update.isPending}
                onChange={(e) => setMessage(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                用完即擋時，web / widget / LINE 三通路顯示的固定文字
              </p>
            </div>
            {error && (
              <p className="rounded bg-destructive/10 p-2 text-sm text-destructive">
                {error}
              </p>
            )}
            {saved && !dirty && (
              <p className="text-xs text-emerald-600">已儲存</p>
            )}
            <Button onClick={handleSave} disabled={!dirty || update.isPending}>
              {update.isPending ? "儲存中..." : "儲存策略"}
            </Button>
          </>
        ) : (
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between rounded-md border p-3">
              <Label htmlFor="policy-auto-topup-readonly">自動展延</Label>
              <Switch
                id="policy-auto-topup-readonly"
                checked={effective === "auto_topup"}
                disabled
              />
            </div>
            {effective === "block" && (
              <p className="rounded bg-muted/50 p-2 text-muted-foreground">
                被擋文案：{quota.block_message || DEFAULT_BLOCK_MESSAGE}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              由方案決定，如需變更請聯繫系統管理員
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
