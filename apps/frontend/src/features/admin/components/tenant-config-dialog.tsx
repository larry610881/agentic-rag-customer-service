import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import { usePlans } from "@/hooks/queries/use-plans";
import { useTenantQuota } from "@/hooks/queries/use-tenant-quota";
import { USAGE_CATEGORIES } from "@/constants/usage-categories";
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
import { Checkbox } from "@/components/ui/checkbox";
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
  included_categories?: string[] | null;
}

function formatTokens(n: number): string {
  if (Math.abs(n) >= 100_000_000) return `${(n / 100_000_000).toFixed(2)} 億`;
  if (Math.abs(n) >= 10_000) return `${(n / 10_000).toFixed(1)} 萬`;
  return n.toLocaleString();
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
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [categoriesEnabled, setCategoriesEnabled] = useState(false);
  const [selectedCats, setSelectedCats] = useState<Set<string>>(new Set());

  const { data: plans } = usePlans(false);
  // S-Token-Gov.2: 載入本月用量
  const { data: quota } = useTenantQuota(tenant?.id ?? null, open);

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
      if (tenant) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.tenants.quota(tenant.id),
        });
      }
      onOpenChange(false);
    },
  });

  useEffect(() => {
    if (open && tenant) {
      setLimit(tenant.monthly_token_limit?.toString() ?? "");
      setPlan(tenant.plan ?? "");
      // included_categories: NULL → 全計入；list → 顯式選擇
      const cats = tenant.included_categories;
      if (cats !== null && cats !== undefined) {
        setCategoriesEnabled(true);
        // 過濾 legacy 值（例如刪除 OTHER 前殘留的 "other"），
        // 只保留 UI 認識的 12 個 — admin 儲存時會自然清掉殘留
        const validValues = new Set(USAGE_CATEGORIES.map((c) => c.value));
        setSelectedCats(new Set(cats.filter((c) => validValues.has(c))));
      } else {
        setCategoriesEnabled(false);
        setSelectedCats(new Set(USAGE_CATEGORIES.map((c) => c.value)));
      }
      setShowAdvanced(false);
    }
  }, [open, tenant]);

  const handleSave = () => {
    const value = limit.trim() === "" ? null : parseInt(limit, 10);
    if (value !== null && isNaN(value)) return;
    const body: UpdateTenantConfigBody = { monthly_token_limit: value };
    if (plan && plan !== tenant?.plan) {
      body.plan = plan;
    }
    // Bug 1 修復：只要 admin 展開過「進階」就送 included_categories，
    // 區分「啟用自訂」=list 與「取消自訂」=null（全計入）。未展開則不送，
    // 後端用 Pydantic model_fields_set 判斷「未傳」→ 維持 tenant 既有值。
    if (showAdvanced) {
      body.included_categories = categoriesEnabled
        ? Array.from(selectedCats)
        : null;
    }
    mutation.mutate(body);
  };

  const toggleCat = (value: string) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const selectedPlan = plans?.find((p) => p.name === plan);

  // 計算進度條百分比（base 用了多少）
  const basePct = useMemo(() => {
    if (!quota || quota.base_total === 0) return 0;
    const used = quota.base_total - quota.base_remaining;
    return Math.min(100, Math.max(0, (used / quota.base_total) * 100));
  }, [quota]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>租戶設定 — {tenant?.name}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* S-Token-Gov.2: 本月用量唯讀區塊 */}
          {quota && (
            <div className="rounded-md border bg-muted/30 p-3">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="font-medium">本月額度</span>
                <span className="font-mono text-muted-foreground">
                  {quota.cycle_year_month} · plan={quota.plan_name}
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="mb-0.5 flex justify-between text-xs">
                    <span>基礎額度</span>
                    <span className="font-mono">
                      {formatTokens(quota.base_remaining)} /{" "}
                      {formatTokens(quota.base_total)} 剩餘
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded bg-muted">
                    <div
                      className={
                        basePct >= 90
                          ? "h-full bg-destructive"
                          : basePct >= 70
                            ? "h-full bg-yellow-500"
                            : "h-full bg-emerald-500"
                      }
                      style={{ width: `${basePct}%` }}
                    />
                  </div>
                </div>
                <div className="flex justify-between text-xs">
                  <span>加值包餘額</span>
                  <span
                    className={
                      quota.addon_remaining < 0
                        ? "font-mono font-medium text-destructive"
                        : "font-mono"
                    }
                  >
                    {formatTokens(quota.addon_remaining)}
                    {quota.addon_remaining < 0 && " (超用)"}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span>本月累計用量</span>
                  <span className="font-mono">
                    {formatTokens(quota.total_used_in_cycle)}
                  </span>
                </div>
              </div>
            </div>
          )}

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

          {/* S-Token-Gov.2: 進階 — 自訂計費 categories（漸進式 disclosure） */}
          <div className="rounded-md border p-3">
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="flex w-full items-center gap-2 text-left text-sm font-medium"
            >
              {showAdvanced ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              進階：自訂計費 category
            </button>
            {showAdvanced && (
              <div className="mt-3 space-y-3">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="categories-enabled"
                    checked={categoriesEnabled}
                    onCheckedChange={(v) => setCategoriesEnabled(v === true)}
                  />
                  <Label
                    htmlFor="categories-enabled"
                    className="cursor-pointer text-xs"
                  >
                    啟用自訂模式（不啟用 = 全部 category 都計入額度）
                  </Label>
                </div>
                {categoriesEnabled && (
                  <div className="space-y-1.5 pl-6">
                    <p className="text-xs text-muted-foreground">
                      勾選的 category 會計入該租戶總額度；取消勾選 = 該 category 免計費
                    </p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {USAGE_CATEGORIES.map((cat) => (
                        <div
                          key={cat.value}
                          className="flex items-center gap-2"
                        >
                          <Checkbox
                            id={`cat-${cat.value}`}
                            checked={selectedCats.has(cat.value)}
                            onCheckedChange={() => toggleCat(cat.value)}
                          />
                          <Label
                            htmlFor={`cat-${cat.value}`}
                            className="cursor-pointer text-xs"
                          >
                            {cat.label}
                          </Label>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
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
