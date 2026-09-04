/** Issue #68 P7c — 異常控管設定鍵的中文標籤、分組與型別描述 */

import type { AbuseControlItem } from "@/types/abuse-control";
import { ApiError } from "@/lib/api-client";

export type AbuseFieldKind = "mode" | "boolean" | "number" | "level" | "string-list";

export interface AbuseFieldDef {
  key: string;
  label: string;
  kind: AbuseFieldKind;
  /** 未在後端 bounds 出現時使用的預設範圍（weight_* 0–50、max_level_* 0–4） */
  fallbackBounds?: [number, number];
  hint?: string;
}

export interface AbuseFieldGroup {
  key: string;
  label: string;
  fields: AbuseFieldDef[];
}

const weight = (signal: string, label: string): AbuseFieldDef => ({
  key: `weight_${signal}`,
  label,
  kind: "number",
  fallbackBounds: [0, 50],
});

const maxLevel = (kind: string, label: string): AbuseFieldDef => ({
  key: `max_level_${kind}`,
  label,
  kind: "level",
  fallbackBounds: [0, 4],
});

export const ABUSE_FIELD_GROUPS: AbuseFieldGroup[] = [
  {
    key: "mode",
    label: "模式與開關",
    fields: [
      { key: "mode", label: "模式", kind: "mode", hint: "監控只記錄不動作；執行才會降速／冷卻／封鎖" },
      { key: "enabled", label: "啟用控管", kind: "boolean" },
    ],
  },
  {
    key: "thresholds",
    label: "門檻與持續",
    fields: [
      { key: "threshold_l1", label: "門檻 L1 觀察", kind: "number" },
      { key: "threshold_l2", label: "門檻 L2 降速", kind: "number" },
      { key: "threshold_l3", label: "門檻 L3 冷卻", kind: "number" },
      { key: "threshold_l4", label: "門檻 L4 封鎖", kind: "number" },
      { key: "duration_l2", label: "持續秒數 L2", kind: "number" },
      { key: "duration_l3", label: "持續秒數 L3", kind: "number" },
      { key: "duration_l4", label: "持續秒數 L4", kind: "number" },
      { key: "decay_per_minute", label: "每分鐘衰減", kind: "number" },
      { key: "pacing_max_per_minute", label: "每分鐘訊息上限", kind: "number" },
      { key: "unrouted_free_count", label: "無法分流免計句數", kind: "number" },
      { key: "slow_requests_per_minute", label: "L2 速率上限", kind: "number" },
      { key: "line_silent_on_cooldown", label: "LINE 冷卻時靜默", kind: "boolean" },
    ],
  },
  {
    key: "weights",
    label: "訊號加分",
    fields: [
      weight("guard_hit", "防護命中"),
      weight("attack", "攻擊判定"),
      weight("pacing", "節奏異常"),
      weight("unrouted", "無法分流"),
      weight("origin_mismatch", "Origin 不符"),
      weight("identify_fail", "身分驗證失敗"),
    ],
  },
  {
    key: "max-levels",
    label: "主體上限",
    fields: [
      maxLevel("visitor", "訪客"),
      maxLevel("end_user", "終端使用者"),
      maxLevel("line_user", "LINE 使用者"),
      maxLevel("user", "後台使用者"),
      maxLevel("client", "API client"),
      maxLevel("ip", "IP"),
      maxLevel("tenant", "租戶"),
    ],
  },
  {
    key: "ip-layer",
    label: "IP 層",
    fields: [
      { key: "ip_layer_enabled", label: "啟用 IP 層", kind: "boolean" },
      { key: "ip_allowlist", label: "IP 白名單", kind: "string-list", hint: "一行一個 IP 或 CIDR" },
    ],
  },
];

/** 後端 ALLOWED_KEYS 含 profile（租戶方案，另由方案選單處理），不在表單顯示 */
const HIDDEN_KEYS = new Set(["profile"]);

export const KNOWN_FIELD_KEYS = new Set(
  ABUSE_FIELD_GROUPS.flatMap((g) => g.fields.map((f) => f.key)),
);

/**
 * 依後端 allowed_keys 補上前端不認識的鍵（例如未來新增的數值鍵），
 * 歸入「其他」群組並以數值輸入呈現——新鍵免改前端即可設定。
 */
export function buildFieldGroups(allowedKeys?: string[]): AbuseFieldGroup[] {
  if (!allowedKeys) return ABUSE_FIELD_GROUPS;
  const extra = allowedKeys
    .filter((k) => !KNOWN_FIELD_KEYS.has(k) && !HIDDEN_KEYS.has(k))
    .sort()
    .map<AbuseFieldDef>((k) => ({ key: k, label: k, kind: "number" }));
  if (extra.length === 0) return ABUSE_FIELD_GROUPS;
  return [...ABUSE_FIELD_GROUPS, { key: "other", label: "其他", fields: extra }];
}

export const FIELD_LABELS: Record<string, string> = Object.fromEntries(
  ABUSE_FIELD_GROUPS.flatMap((g) =>
    g.fields.map((f) => [
      f.key,
      g.key === "weights" ? `訊號加分：${f.label}` : g.key === "max-levels" ? `最高等級：${f.label}` : f.label,
    ]),
  ),
);

export function fieldLabel(key: string): string {
  return FIELD_LABELS[key] ?? key;
}

export const LEVEL_LABELS: Record<number, string> = {
  0: "無",
  1: "觀察",
  2: "降速",
  3: "冷卻",
  4: "封鎖",
};

export function levelLabel(level: number): string {
  return LEVEL_LABELS[level] ?? `L${level}`;
}

export const MODE_LABELS: Record<string, string> = {
  monitor: "監控",
  enforce: "執行",
};

export const SUBJECT_KIND_LABELS: Record<string, string> = {
  visitor: "訪客",
  end_user: "終端使用者",
  line_user: "LINE 使用者",
  user: "後台使用者",
  client: "API client",
  ip: "IP",
  tenant: "租戶",
};

export function subjectKindLabel(kind: string): string {
  return SUBJECT_KIND_LABELS[kind] ?? kind;
}

export const BUILTIN_PROFILE_NAMES = new Set(["standard", "strict", "lenient", "monitor"]);

export const PROFILE_LABELS: Record<string, string> = {
  standard: "標準",
  strict: "嚴格",
  lenient: "寬鬆",
  monitor: "僅監控",
};

export function profileLabel(name: string): string {
  const zh = PROFILE_LABELS[name];
  return zh ? `${name}（${zh}）` : name;
}

/** 依鍵型別把設定值轉成可讀字串（列表 / 生效表用） */
export function formatSettingValue(key: string, value: unknown): string {
  if (value === undefined || value === null) return "—";
  if (key === "mode" && typeof value === "string") return MODE_LABELS[value] ?? value;
  if (key.startsWith("max_level_") && typeof value === "number") {
    return `${value}（${levelLabel(value)}）`;
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "（空）";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** 剩餘秒數 → mm:ss（滿一小時加 hh:） */
export function formatRemaining(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mmss = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return h > 0 ? `${h}:${mmss}` : mmss;
}

export function controlKey(item: AbuseControlItem): string {
  return `${item.tenant_id}|${item.subject_kind}|${item.subject_id ?? item.subject_masked}`;
}

/** 422 回 { detail: string }；其餘以狀態碼給通用訊息 */
export function describeAbuseApiError(err: unknown, fallback = "儲存失敗"): string {
  if (err instanceof ApiError) {
    if (err.status === 422) {
      try {
        const parsed = JSON.parse(err.message) as { detail?: unknown };
        if (typeof parsed.detail === "string") return parsed.detail;
      } catch {
        /* body 不是 JSON，落到下方 */
      }
      return "欄位驗證失敗，請檢查數值範圍";
    }
    if (err.status === 403) return "沒有權限執行此操作";
  }
  return fallback;
}
