import type {
  BillingMode,
  ExhaustionPolicy,
  PlanBillingFields,
} from "@/types/billing";

/** Issue #74：計價 / 用盡策略欄位見 `PlanBillingFields` */
export interface Plan extends PlanBillingFields {
  id: string;
  name: string;
  base_monthly_tokens: number;
  addon_pack_tokens: number;
  base_price: string; // Decimal serialized as string
  addon_price: string;
  currency: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Issue #74：建立 / 更新時可一併送計價與用盡策略欄位（皆可省略，後端有預設） */
export interface PlanBillingRequestFields {
  billing_mode?: BillingMode;
  monthly_points?: number;
  addon_pack_points?: number;
  default_category_multiplier?: number;
  exhaustion_policy?: ExhaustionPolicy;
  tenant_may_change_policy?: boolean;
  auto_topup_monthly_cap?: number;
  grace_percent?: number;
  block_message?: string;
}

export interface CreatePlanRequest extends PlanBillingRequestFields {
  name: string;
  base_monthly_tokens: number;
  addon_pack_tokens: number;
  base_price: number;
  addon_price: number;
  currency?: string;
  description?: string | null;
  is_active?: boolean;
}

export interface UpdatePlanRequest extends PlanBillingRequestFields {
  base_monthly_tokens?: number;
  addon_pack_tokens?: number;
  base_price?: number;
  addon_price?: number;
  currency?: string;
  description?: string | null;
  is_active?: boolean;
}
