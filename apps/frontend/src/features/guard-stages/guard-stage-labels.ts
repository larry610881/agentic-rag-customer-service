/** Issue #75 — 防護階段的中文標籤、說明、成本提示與來源標籤 */

import { ApiError } from "@/lib/api-client";
import type { GuardStage, GuardStageSource } from "@/types/guard-stages";

export interface GuardStageDef {
  key: GuardStage;
  label: string;
  /** 一句話說明這段防護做什麼 */
  description: string;
  /** 每題額外成本（無成本者為 undefined） */
  costHint?: string;
  /** 預留階段：顯示「即將推出」且不可勾選 */
  comingSoon?: boolean;
}

/** 顯示順序 = 管線執行順序 */
export const GUARD_STAGE_DEFS: GuardStageDef[] = [
  {
    key: "regex_input",
    label: "正則輸入防護",
    description: "以規則比對攔截明顯的注入、越權與敏感字串，零成本。",
  },
  {
    key: "classifier_attack",
    label: "分類器攻擊判定",
    description: "由小模型判定訊息是否為攻擊（角色劫持、提示詞外洩等）。",
    costHint: "每題多一次小模型呼叫",
  },
  {
    key: "output_guard",
    label: "輸出防護",
    description: "回覆送出前檢查是否洩漏系統提示詞或違規內容，零成本。",
  },
  {
    key: "abuse_scoring",
    label: "異常計分",
    description: "累計異常行為分數並依門檻降速、冷卻、封鎖（見異常控管）。",
  },
  {
    key: "local_classifier",
    label: "地端小模型判定",
    description: "以地端部署的小模型做攻擊判定，不經外部 API。",
    comingSoon: true,
  },
];

export const GUARD_STAGE_ORDER: string[] = GUARD_STAGE_DEFS.map((d) => d.key);

const DEF_BY_KEY = new Map<string, GuardStageDef>(GUARD_STAGE_DEFS.map((d) => [d.key, d]));

export function guardStageDef(key: string): GuardStageDef | undefined {
  return DEF_BY_KEY.get(key);
}

/** 未知階段（後端新增、前端尚未對照）直接回傳 key，免改前端即可顯示 */
export function guardStageLabel(key: string): string {
  return DEF_BY_KEY.get(key)?.label ?? key;
}

/** 依管線順序排序（未知階段排最後、依字母序） */
export function sortGuardStages(stages: Iterable<string>): string[] {
  const rank = (k: string) => {
    const i = GUARD_STAGE_ORDER.indexOf(k);
    return i === -1 ? GUARD_STAGE_ORDER.length : i;
  };
  return Array.from(new Set(stages)).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

export const GUARD_SOURCE_LABELS: Record<GuardStageSource, string> = {
  required: "底線",
  platform: "系統預設",
  profile: "方案",
  tenant: "租戶啟用",
  bot: "Bot 加嚴",
  fallback: "失效保護（全開）",
};

export function guardSourceLabel(source: string | undefined): string {
  if (!source) return "未啟用";
  return (GUARD_SOURCE_LABELS as Record<string, string>)[source] ?? source;
}

/** 內建方案說明（名稱來自後端 builtin_profiles） */
export const GUARD_PROFILE_DESCRIPTIONS: Record<string, string> = {
  standard: "沿用系統預設",
  exhibition: "展覽用：不跑分類器攻擊判定（省一次小模型呼叫）",
};

export function guardProfileDescription(name: string, overrides?: { stages?: string[] }): string {
  const known = GUARD_PROFILE_DESCRIPTIONS[name];
  if (known) return known;
  return overrides?.stages ? "自訂預設階段" : "沿用系統預設";
}

/** 勾選清單的全集：後端 available_stages / stages 優先，缺時退回前端宣告；未知階段以 key 顯示 */
export function guardStageDefsFor(universe?: string[]): GuardStageDef[] {
  if (!universe || universe.length === 0) return GUARD_STAGE_DEFS;
  return sortGuardStages(universe).map(
    (key) =>
      DEF_BY_KEY.get(key) ?? ({ key: key as GuardStage, label: key, description: "" } as GuardStageDef),
  );
}

/** kb 模式提示：分類器預設不跑，對外 bot 建議勾選 */
export const KB_MODE_GUARD_HINT =
  "知識庫問答模式預設不跑分類器；對外 bot 建議勾選分類器攻擊判定";

export const GUARD_LOCKED_HINT = "由系統管理員設定";

export function describeGuardApiError(err: unknown, fallback = "儲存失敗"): string {
  if (err instanceof ApiError) {
    if (err.status === 422) {
      try {
        const parsed = JSON.parse(err.message) as { detail?: unknown };
        if (typeof parsed.detail === "string") return parsed.detail;
      } catch {
        /* body 不是 JSON，落到下方 */
      }
      return "設定驗證失敗，請檢查底線與階段清單";
    }
    if (err.status === 403) return "沒有權限執行此操作";
  }
  return fallback;
}
