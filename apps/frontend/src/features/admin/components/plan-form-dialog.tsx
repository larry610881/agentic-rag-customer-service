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
import type { Plan } from "@/types/plan";

interface PlanFormDialogProps {
  /** null = 新增模式；非 null = 編輯該 plan */
  plan: Plan | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_FORM = {
  name: "",
  base_monthly_tokens: 10_000_000,
  addon_pack_tokens: 5_000_000,
  base_price: 0,
  addon_price: 0,
  currency: "TWD",
  description: "",
  is_active: true,
};

export function PlanFormDialog({
  plan,
  open,
  onOpenChange,
}: PlanFormDialogProps) {
  const isEdit = plan !== null;
  const [form, setForm] = useState({ ...DEFAULT_FORM });
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreatePlan();
  const updateMutation = useUpdatePlan();
  const pending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (open) {
      setError(null);
      if (plan) {
        setForm({
          name: plan.name,
          base_monthly_tokens: plan.base_monthly_tokens,
          addon_pack_tokens: plan.addon_pack_tokens,
          base_price: Number(plan.base_price),
          addon_price: Number(plan.addon_price),
          currency: plan.currency,
          description: plan.description ?? "",
          is_active: plan.is_active,
        });
      } else {
        setForm({ ...DEFAULT_FORM });
      }
    }
  }, [open, plan]);

  const handleSave = async () => {
    setError(null);
    try {
      if (isEdit && plan) {
        await updateMutation.mutateAsync({
          id: plan.id,
          data: {
            base_monthly_tokens: form.base_monthly_tokens,
            addon_pack_tokens: form.addon_pack_tokens,
            base_price: form.base_price,
            addon_price: form.addon_price,
            currency: form.currency,
            description: form.description || null,
            is_active: form.is_active,
          },
        });
      } else {
        await createMutation.mutateAsync({
          name: form.name.trim(),
          base_monthly_tokens: form.base_monthly_tokens,
          addon_pack_tokens: form.addon_pack_tokens,
          base_price: form.base_price,
          addon_price: form.addon_price,
          currency: form.currency,
          description: form.description || null,
          is_active: form.is_active,
        });
      }
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "儲存失敗");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
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
              onChange={(e) => setForm({ ...form, name: e.target.value })}
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
                onChange={(e) =>
                  setForm({
                    ...form,
                    base_monthly_tokens: Number(e.target.value),
                  })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="addon-tokens">加值包額度 (token)</Label>
              <Input
                id="addon-tokens"
                type="number"
                value={form.addon_pack_tokens}
                onChange={(e) =>
                  setForm({
                    ...form,
                    addon_pack_tokens: Number(e.target.value),
                  })
                }
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
                onChange={(e) =>
                  setForm({ ...form, base_price: Number(e.target.value) })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="addon-price">加值包價格</Label>
              <Input
                id="addon-price"
                type="number"
                step="0.01"
                value={form.addon_price}
                onChange={(e) =>
                  setForm({ ...form, addon_price: Number(e.target.value) })
                }
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="currency">幣別</Label>
            <Input
              id="currency"
              value={form.currency}
              maxLength={3}
              onChange={(e) =>
                setForm({ ...form, currency: e.target.value.toUpperCase() })
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">說明</Label>
            <Textarea
              id="description"
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
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
              onCheckedChange={(v) => setForm({ ...form, is_active: v })}
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
