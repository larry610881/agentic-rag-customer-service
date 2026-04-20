import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import { usePlans } from "@/hooks/queries/use-plans";
import type { Tenant } from "@/types/auth";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface TenantConfigDialogProps {
  tenant: Tenant | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface UpdateTenantConfigBody {
  plan?: string | null;
  monthly_token_limit: number | null;
}

export function TenantConfigDialog({
  tenant,
  open,
  onOpenChange,
}: TenantConfigDialogProps) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState<string>("");
  const [plan, setPlan] = useState<string>("");

  // Token-Gov.1: 載入啟用中的 plan 給下拉選用
  const { data: plans } = usePlans(false);

  const mutation = useMutation({
    mutationFn: (data: UpdateTenantConfigBody) =>
      apiFetch<Tenant>(
        API_ENDPOINTS.tenants.config(tenant?.id ?? ""),
        {
          method: "PATCH",
          body: JSON.stringify(data),
        },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.all });
      onOpenChange(false);
    },
  });

  const handleOpen = (isOpen: boolean) => {
    if (isOpen && tenant) {
      setLimit(tenant.monthly_token_limit?.toString() ?? "");
      setPlan(tenant.plan ?? "");
    }
    onOpenChange(isOpen);
  };

  const handleSave = () => {
    const value = limit.trim() === "" ? null : parseInt(limit, 10);
    if (value !== null && isNaN(value)) return;
    const body: UpdateTenantConfigBody = { monthly_token_limit: value };
    if (plan && plan !== tenant?.plan) {
      body.plan = plan;
    }
    mutation.mutate(body);
  };

  const selectedPlan = plans?.find((p) => p.name === plan);

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>租戶設定 — {tenant?.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="plan-select">方案</Label>
            <Select value={plan} onValueChange={setPlan}>
              <SelectTrigger id="plan-select">
                <SelectValue placeholder="選擇方案..." />
              </SelectTrigger>
              <SelectContent>
                {plans?.map((p) => (
                  <SelectItem key={p.id} value={p.name}>
                    {p.name} — 月 {(p.base_monthly_tokens / 10_000).toFixed(0)} 萬 token
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedPlan && (
              <p className="text-xs text-muted-foreground">
                月基礎額度 {selectedPlan.base_monthly_tokens.toLocaleString()} /
                加值包 {selectedPlan.addon_pack_tokens.toLocaleString()} —
                {Number(selectedPlan.base_price).toLocaleString()} {selectedPlan.currency}/月
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="monthly-limit">每月 Token 上限</Label>
            <Input
              id="monthly-limit"
              type="number"
              placeholder="不設定（沿用方案的 base_monthly_tokens）"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              留空表示沿用方案。手動填數值時會覆蓋方案的月度額度上限（fallback hard cap）。
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={mutation.isPending}>
            {mutation.isPending ? "儲存中..." : "儲存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
