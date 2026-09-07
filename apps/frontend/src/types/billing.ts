/**
 * Issue #74 — 雙軌計價（token / 點數）+ 額度用盡策略
 *
 * 對應後端 `plan_router.py` / `billing_admin_router.py` / `tenant_router.py`。
 * 後端以 Pydantic Decimal 序列化的欄位（倍率、grace_percent、usd_per_point）
 * 可能是字串，使用端一律 `Number()` 包一層。
 */

export type BillingMode = "token" | "points";

export type ExhaustionPolicy = "auto_topup" | "block";

/** 方案物件新增的計價 / 用盡策略欄位（與 `Plan` 合併） */
export interface PlanBillingFields {
  billing_mode: BillingMode;
  /** 點數制：每月基本點數 */
  monthly_points: number;
  /** 點數制：加購點數包 */
  addon_pack_points: number;
  /** 點數制：未在類別倍率表指定時的預設倍率（可能為 Decimal 字串） */
  default_category_multiplier: number | string;
  exhaustion_policy: ExhaustionPolicy;
  /** 租戶是否可自行切換用盡策略 */
  tenant_may_change_policy: boolean;
  /** 自動展延每月上限（0 = 不限） */
  auto_topup_monthly_cap: number;
  /** 寬限百分比（0–100，可能為 Decimal 字串） */
  grace_percent: number | string;
  /** 用完即擋時給終端使用者看的文案 */
  block_message: string;
}

/** category → 倍率；未列出的類別沿用 default_category_multiplier */
export type PlanMultiplierMap = Record<string, number | string>;

/** GET/PUT /api/v1/admin/plans/{plan_id}/multipliers 回應 */
export interface PlanMultipliersResponse {
  plan_id: string;
  default_category_multiplier: number | string;
  multipliers: PlanMultiplierMap;
}

/** PUT body — 整份取代；未知 / 已棄用類別 → 422 */
export interface ReplacePlanMultipliersRequest {
  multipliers: Record<string, number>;
}

/** GET/PUT /api/v1/admin/billing/settings */
export interface BillingSettings {
  usd_per_point: number | string;
  updated_by: string | null;
  updated_at: string;
}

export interface UpdateBillingSettingsRequest {
  usd_per_point: number;
}

/** PUT /api/v1/tenants/{tenant_id}/billing-policy body；null = 清除覆寫（沿用方案） */
export interface UpdateTenantBillingPolicyRequest {
  exhaustion_policy: ExhaustionPolicy | null;
  block_message: string | null;
}

export interface TenantBillingPolicyResponse {
  tenant_id: string;
  exhaustion_policy_override: ExhaustionPolicy | null;
  block_message_override: string | null;
  effective_policy: ExhaustionPolicy;
  block_message: string;
  tenant_may_change_policy: boolean;
}

/**
 * 租戶額度快照新增的計價欄位（與 `TenantQuota` 合併）。
 * 全部 optional：後端有預設值，且舊快照（未升級）缺欄位時頁面退回 token 制。
 */
export interface TenantQuotaBillingFields {
  billing_mode?: BillingMode;
  /** 方案預設策略 */
  exhaustion_policy?: ExhaustionPolicy;
  /** 租戶覆寫後實際生效的策略 — 徽章 / 開關以此為準 */
  effective_policy?: ExhaustionPolicy;
  tenant_may_change_policy?: boolean;
  grace_percent?: number;
  block_message?: string;
  /** 點數制才有意義（token 制為 0） */
  points_total?: number;
  points_used?: number;
  points_remaining?: number;
}

/** 非串流 402 回應 body */
export interface QuotaExhaustedBody {
  detail: "quota_exhausted";
  message: string;
}
