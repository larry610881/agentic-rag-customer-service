/** Issue #74 — 雙軌計價 / 額度用盡策略的中文標籤與格式化 */

import { ApiError } from "@/lib/api-client";
import type {
  BillingMode,
  ExhaustionPolicy,
  PlanMultiplierMap,
} from "@/types/billing";

export const BILLING_MODE_LABELS: Record<BillingMode, string> = {
  token: "Token 制",
  points: "點數制",
};

export function billingModeLabel(mode: string | null | undefined): string {
  if (!mode) return BILLING_MODE_LABELS.token;
  return BILLING_MODE_LABELS[mode as BillingMode] ?? mode;
}

export const EXHAUSTION_POLICY_LABELS: Record<ExhaustionPolicy, string> = {
  auto_topup: "自動展延",
  block: "用完即擋",
};

export const EXHAUSTION_POLICY_HINTS: Record<ExhaustionPolicy, string> = {
  auto_topup: "額度用完自動加購加值包，受每月上限限制",
  block: "額度用完即停止服務，終端使用者會看到被擋文案",
};

export function exhaustionPolicyLabel(policy: string | null | undefined): string {
  if (!policy) return "—";
  return EXHAUSTION_POLICY_LABELS[policy as ExhaustionPolicy] ?? policy;
}

/** 租戶頁：null = 沿用方案 */
export const TENANT_POLICY_OVERRIDE_OPTIONS: readonly {
  value: "" | ExhaustionPolicy;
  label: string;
}[] = [
  { value: "", label: "沿用方案" },
  { value: "auto_topup", label: EXHAUSTION_POLICY_LABELS.auto_topup },
  { value: "block", label: EXHAUSTION_POLICY_LABELS.block },
];

export const DEFAULT_BLOCK_MESSAGE = "本月額度已用完，服務暫停，請聯繫管理員。";

/** 點數以整數千分位顯示 */
export function formatPoints(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString();
}

/** 自動展延月上限：0 = 不限 */
export function formatTopupCap(cap: number | null | undefined): string {
  if (cap === null || cap === undefined || cap <= 0) return "不限";
  return `${cap.toLocaleString()} 次 / 月`;
}

/** 匯率：1 點 = X USD；小數位依大小自適應（最多 6 位） */
export function formatUsdPerPoint(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || Number.isNaN(rate)) return "—";
  const digits = rate >= 1 ? 2 : rate >= 0.01 ? 4 : 6;
  return `1 點 = ${rate.toFixed(digits)} USD`;
}

/** 倍率：整數不留小數，否則最多 3 位；null/undefined 表示沿用預設 */
export function formatMultiplier(m: number | null | undefined): string {
  if (m === null || m === undefined || Number.isNaN(m)) return "預設";
  return Number.isInteger(m) ? `${m}×` : `${parseFloat(m.toFixed(3))}×`;
}

/** 已用百分比（0–100，超用封頂 100）；total 為 0 視為 0% */
export function usedPercent(used: number, total: number): number {
  if (!total || total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((used / total) * 100)));
}

/**
 * 倍率表單 → PUT body 的 `multipliers` dict。
 * 表單以 `Record<category, string>` 保存輸入原文；空字串 = 沿用預設倍率（不送）。
 * 非數字 / 負數的輸入回傳 error，由呼叫端擋下送出。
 */
export function buildMultiplierPayload(
  form: Record<string, string>,
): { multipliers: Record<string, number>; error: string | null } {
  const multipliers: Record<string, number> = {};
  for (const [usage_category, raw] of Object.entries(form)) {
    const text = raw.trim();
    if (text === "") continue;
    const multiplier = Number(text);
    if (!Number.isFinite(multiplier) || multiplier < 0) {
      return { multipliers: {}, error: `類別倍率「${usage_category}」必須是 ≥ 0 的數字` };
    }
    multipliers[usage_category] = multiplier;
  }
  return { multipliers, error: null };
}

/** 後端倍率 dict → 表單初始值（未列出的類別留空 = 沿用預設；Decimal 字串正規化） */
export function multipliersToForm(
  multipliers: PlanMultiplierMap | undefined,
  categories: readonly string[],
): Record<string, string> {
  return Object.fromEntries(
    categories.map((c) => {
      const v = multipliers?.[c];
      return [c, v === undefined || v === null ? "" : String(Number(v))];
    }),
  );
}

/**
 * 非串流 402 `{ detail: "quota_exhausted", message }` → 文案；不是額度用盡回 null。
 * apiFetch 把回應 body 放在 ApiError.message。
 */
export function quotaExhaustedMessage(err: unknown): string | null {
  if (!(err instanceof ApiError) || err.status !== 402) return null;
  try {
    const parsed = JSON.parse(err.message) as { detail?: unknown; message?: unknown };
    if (parsed.detail !== "quota_exhausted") return null;
    return typeof parsed.message === "string" && parsed.message
      ? parsed.message
      : DEFAULT_BLOCK_MESSAGE;
  } catch {
    return DEFAULT_BLOCK_MESSAGE;
  }
}

/** 403 = 方案不允許租戶自改；422 取 detail；其餘用 fallback */
export function describeBillingApiError(err: unknown, fallback = "儲存失敗"): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "方案不允許租戶自行變更用盡策略";
    if (err.status === 422) {
      try {
        const parsed = JSON.parse(err.message) as { detail?: unknown };
        if (typeof parsed.detail === "string") return parsed.detail;
      } catch {
        /* body 不是 JSON */
      }
      return "欄位驗證失敗，請檢查數值範圍";
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
