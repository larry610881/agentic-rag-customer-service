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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useCreatePlan, useUpdatePlan } from "@/hooks/queries/use-plans";
import {
  usePlanMultipliers,
  useReplacePlanMultipliers,
} from "@/hooks/queries/use-plan-multipliers";
import { USAGE_CATEGORIES } from "@/constants/usage-categories";
import { PlanCategoryMultiplierTable } from "@/features/billing/components/plan-category-multiplier-table";
import {
  BILLING_MODE_LABELS,
  DEFAULT_BLOCK_MESSAGE,
  EXHAUSTION_POLICY_HINTS,
  EXHAUSTION_POLICY_LABELS,
  buildMultiplierPayload,
  describeBillingApiError,
  multipliersToForm,
} from "@/features/billing/billing-labels";
import type { Plan, PlanBillingRequestFields } from "@/types/plan";
import type { BillingMode, ExhaustionPolicy } from "@/types/billing";

interface PlanFormDialogProps {
  /** null = 新增模式；非 null = 編輯該 plan */
  plan: Plan | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const CATEGORY_VALUES = USAGE_CATEGORIES.map((c) => c.value);

const DEFAULT_FORM = {
  name: "",
  base_monthly_tokens: 10_000_000,
  addon_pack_tokens: 5_000_000,
  base_price: 0,
  addon_price: 0,
  currency: "TWD",
  description: "",
  is_active: true,
  // Issue #74 — 計價
  billing_mode: "token" as BillingMode,
  monthly_points: 0,
  addon_pack_points: 0,
  default_category_multiplier: 1,
  // Issue #74 — 額度用盡策略
  exhaustion_policy: "auto_topup" as ExhaustionPolicy,
  tenant_may_change_policy: false,
  auto_topup_monthly_cap: 0,
  grace_percent: 0,
  block_message: "",
};

type PlanForm = typeof DEFAULT_FORM;

function formFromPlan(plan: Plan): PlanForm {
  return {
    name: plan.name,
    base_monthly_tokens: plan.base_monthly_tokens,
    addon_pack_tokens: plan.addon_pack_tokens,
    base_price: Number(plan.base_price),
    addon_price: Number(plan.addon_price),
    currency: plan.currency,
    description: plan.description ?? "",
    is_active: plan.is_active,
    billing_mode: plan.billing_mode ?? "token",
    monthly_points: plan.monthly_points ?? 0,
    addon_pack_points: plan.addon_pack_points ?? 0,
    default_category_multiplier: Number(plan.default_category_multiplier ?? 1),
    exhaustion_policy: plan.exhaustion_policy ?? "auto_topup",
    tenant_may_change_policy: plan.tenant_may_change_policy ?? false,
    auto_topup_monthly_cap: plan.auto_topup_monthly_cap ?? 0,
    grace_percent: Number(plan.grace_percent ?? 0),
    block_message: plan.block_message ?? "",
  };
}

function billingFieldsFromForm(form: PlanForm): Required<PlanBillingRequestFields> {
  return {
    billing_mode: form.billing_mode,
    monthly_points: form.monthly_points,
    addon_pack_points: form.addon_pack_points,
    default_category_multiplier: form.default_category_multiplier,
    exhaustion_policy: form.exhaustion_policy,
    tenant_may_change_policy: form.tenant_may_change_policy,
    auto_topup_monthly_cap: form.auto_topup_monthly_cap,
    grace_percent: form.grace_percent,
    block_message: form.block_message,
  };
}

export function PlanFormDialog({
  plan,
  open,
  onOpenChange,
}: PlanFormDialogProps) {
  const isEdit = plan !== null;
  const [form, setForm] = useState<PlanForm>({ ...DEFAULT_FORM });
  const [multipliers, setMultipliers] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreatePlan();
  const updateMutation = useUpdatePlan();
  const replaceMultipliers = useReplacePlanMultipliers();
  const multipliersQuery = usePlanMultipliers(plan?.id ?? null, open && isEdit);
  const pending =
    createMutation.isPending ||
    updateMutation.isPending ||
    replaceMultipliers.isPending;

  useEffect(() => {
    if (open) {
      setError(null);
      setForm(plan ? formFromPlan(plan) : { ...DEFAULT_FORM });
    }
  }, [open, plan]);

  useEffect(() => {
    if (!open) return;
    setMultipliers(
      multipliersToForm(
        isEdit ? multipliersQuery.data?.multipliers : undefined,
        CATEGORY_VALUES,
      ),
    );
  }, [open, isEdit, multipliersQuery.data]);

  const isPoints = form.billing_mode === "points";
  const set = <K extends keyof PlanForm>(key: K, value: PlanForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));
  const setNumber = (key: keyof PlanForm) => (e: React.ChangeEvent<HTMLInputElement>) =>
    set(key, Number(e.target.value) as PlanForm[typeof key]);

  const handleSave = async () => {
    setError(null);
    const multiplierPayload = isPoints
      ? buildMultiplierPayload(multipliers)
      : { multipliers: {}, error: null };
    if (multiplierPayload.error) {
      setError(multiplierPayload.error);
      return;
    }
    if (form.grace_percent < 0 || form.grace_percent > 100) {
      setError("寬限百分比必須介於 0–100");
      return;
    }

    try {
      const common = {
        base_monthly_tokens: form.base_monthly_tokens,
        addon_pack_tokens: form.addon_pack_tokens,
        base_price: form.base_price,
        addon_price: form.addon_price,
        currency: form.currency,
        description: form.description || null,
        is_active: form.is_active,
        ...billingFieldsFromForm(form),
      };
      let saved: Plan;
      if (isEdit && plan) {
        saved = await updateMutation.mutateAsync({ id: plan.id, data: common });
      } else {
        saved = await createMutation.mutateAsync({
          name: form.name.trim(),
          ...common,
        });
      }
      // 倍率表在方案存檔後另存（新增模式需先拿到 plan id）
      if (isPoints) {
        await replaceMultipliers.mutateAsync({
          planId: saved?.id ?? plan?.id ?? "",
          data: { multipliers: multiplierPayload.multipliers },
        });
      }
      onOpenChange(false);
    } catch (e) {
      setError(describeBillingApiError(e));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? `編輯方案 — ${plan?.name}` : "新增方案"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="plan-name">名稱 (英數識別碼，唯一)</Label>
            <Input
              id="plan-name"
              value={form.name}
              disabled={isEdit}
              onChange={(e) => set("name", e.target.value)}
              placeholder="例：starter / pro / enterprise"
            />
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                名稱不可改 — 如需更名請刪除重建
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="base-tokens">月基礎額度 (token)</Label>
              <Input
                id="base-tokens"
                type="number"
                value={form.base_monthly_tokens}
                onChange={setNumber("base_monthly_tokens")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="addon-tokens">加值包額度 (token)</Label>
              <Input
                id="addon-tokens"
                type="number"
                value={form.addon_pack_tokens}
                onChange={setNumber("addon_pack_tokens")}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="base-price">月費</Label>
              <Input
                id="base-price"
                type="number"
                step="0.01"
                value={form.base_price}
                onChange={setNumber("base_price")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="addon-price">加值包價格</Label>
              <Input
                id="addon-price"
                type="number"
                step="0.01"
                value={form.addon_price}
                onChange={setNumber("addon_price")}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="currency">幣別</Label>
            <Input
              id="currency"
              value={form.currency}
              maxLength={3}
              onChange={(e) => set("currency", e.target.value.toUpperCase())}
            />
          </div>

          {/* Issue #74 — 計價 */}
          <fieldset className="space-y-3 rounded-md border p-3">
            <legend className="px-1 text-sm font-medium">計價</legend>
            <div
              role="radiogroup"
              aria-label="計價模式"
              className="flex gap-4"
            >
              {(Object.keys(BILLING_MODE_LABELS) as BillingMode[]).map((mode) => (
                <label key={mode} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="billing-mode"
                    value={mode}
                    checked={form.billing_mode === mode}
                    onChange={() => set("billing_mode", mode)}
                  />
                  {BILLING_MODE_LABELS[mode]}
                </label>
              ))}
            </div>
            {isPoints ? (
              <>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="monthly-points">每月基本點數</Label>
                    <Input
                      id="monthly-points"
                      type="number"
                      min="0"
                      value={form.monthly_points}
                      onChange={setNumber("monthly_points")}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="addon-points">加購點數包</Label>
                    <Input
                      id="addon-points"
                      type="number"
                      min="0"
                      value={form.addon_pack_points}
                      onChange={setNumber("addon_pack_points")}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="default-multiplier">預設倍率</Label>
                    <Input
                      id="default-multiplier"
                      type="number"
                      step="0.001"
                      min="0"
                      value={form.default_category_multiplier}
                      onChange={setNumber("default_category_multiplier")}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <p className="text-sm font-medium">類別倍率</p>
                  <p className="text-xs text-muted-foreground">
                    留空 = 沿用預設倍率；0 = 該類別不扣點。方案存檔後另行寫入倍率表。
                  </p>
                  <PlanCategoryMultiplierTable
                    value={multipliers}
                    onChange={setMultipliers}
                    defaultMultiplier={form.default_category_multiplier}
                    disabled={isEdit && multipliersQuery.isLoading}
                  />
                </div>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">
                Token 制以計費 token 扣額度；切換為點數制可設定每月點數與類別倍率。
              </p>
            )}
          </fieldset>

          {/* Issue #74 — 額度用盡策略（兩種計價模式共用） */}
          <fieldset className="space-y-3 rounded-md border p-3">
            <legend className="px-1 text-sm font-medium">額度用盡策略</legend>
            <div
              role="radiogroup"
              aria-label="額度用盡策略"
              className="flex gap-4"
            >
              {(Object.keys(EXHAUSTION_POLICY_LABELS) as ExhaustionPolicy[]).map(
                (policy) => (
                  <label key={policy} className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="exhaustion-policy"
                      value={policy}
                      checked={form.exhaustion_policy === policy}
                      onChange={() => set("exhaustion_policy", policy)}
                    />
                    {EXHAUSTION_POLICY_LABELS[policy]}
                  </label>
                ),
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {EXHAUSTION_POLICY_HINTS[form.exhaustion_policy]}
            </p>

            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="tenant-may-change" className="text-sm">
                  租戶可自行切換
                </Label>
                <p className="text-xs text-muted-foreground">
                  開啟後租戶可在「本月額度」頁自行切換策略與被擋文案
                </p>
              </div>
              <Switch
                id="tenant-may-change"
                checked={form.tenant_may_change_policy}
                onCheckedChange={(v) => set("tenant_may_change_policy", v)}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="topup-cap">自動展延每月上限</Label>
                <Input
                  id="topup-cap"
                  type="number"
                  min="0"
                  value={form.auto_topup_monthly_cap}
                  onChange={setNumber("auto_topup_monthly_cap")}
                />
                <p className="text-xs text-muted-foreground">0 = 不限</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="grace-percent">寬限百分比</Label>
                <Input
                  id="grace-percent"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={form.grace_percent}
                  onChange={setNumber("grace_percent")}
                />
                <p className="text-xs text-muted-foreground">用盡後仍放行的額度比例</p>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="block-message">被擋文案</Label>
              <Textarea
                id="block-message"
                rows={2}
                value={form.block_message}
                placeholder={DEFAULT_BLOCK_MESSAGE}
                onChange={(e) => set("block_message", e.target.value)}
              />
            </div>
          </fieldset>

          <div className="space-y-2">
            <Label htmlFor="description">說明</Label>
            <Textarea
              id="description"
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              placeholder="供 admin 識別此方案用途，例：基礎 / 企業 / 內部測試"
              rows={2}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="is-active" className="text-sm">
                啟用中
              </Label>
              <p className="text-xs text-muted-foreground">
                停用後新租戶無法選此方案，既有綁定不變
              </p>
            </div>
            <Switch
              id="is-active"
              checked={form.is_active}
              onCheckedChange={(v) => set("is_active", v)}
            />
          </div>

          {error && (
            <p className="rounded bg-destructive/10 p-2 text-sm text-destructive">
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={pending}>
            {pending ? "儲存中..." : "儲存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
