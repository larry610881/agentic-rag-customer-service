/** Issue #68 P7c — 異常控管（abuse control）後台設定與受控清單 */

export type AbuseMode = "monitor" | "enforce";

/** 覆寫只存「有改的鍵」；值型別依鍵而異（number / boolean / string / string[]） */
export type AbuseOverrides = Record<string, unknown>;

export interface AbuseSettingsOverview {
  platform_overrides: AbuseOverrides;
  /** 內建方案（standard / strict / lenient / monitor）與 DB 方案合併後的結果 */
  profiles: Record<string, AbuseOverrides>;
  /** 程式常數 + 平台覆寫後的生效預設值 */
  effective_default: Record<string, unknown>;
  allowed_keys: string[];
  /** 數值鍵的 [min, max]；不含 weight_* / max_level_*（前端以固定範圍補） */
  bounds: Record<string, [number, number]>;
}

export interface AbuseSettingsSaved {
  scope_kind: "platform" | "profile" | "tenant";
  scope_id: string;
  overrides: AbuseOverrides;
  updated_at: string;
}

export interface TenantAbuseSettings {
  tenant_id: string;
  profile: string;
  overrides: AbuseOverrides;
  effective: Record<string, unknown>;
  /** 只有 system_admin 為 true */
  editable: boolean;
}

export interface UpdateAbuseOverridesRequest {
  overrides: AbuseOverrides;
}

export interface UpdateTenantAbuseSettingsRequest {
  profile?: string;
  overrides: AbuseOverrides;
}

export type AbuseSubjectKind =
  | "visitor"
  | "end_user"
  | "line_user"
  | "user"
  | "client"
  | "ip"
  | "tenant";

/** 0 無、1 觀察、2 降速、3 冷卻、4 封鎖 */
export type AbuseLevel = 0 | 1 | 2 | 3 | 4;

export interface AbuseControlItem {
  tenant_id: string;
  subject_kind: AbuseSubjectKind | string;
  /** tenant_admin 讀取時為 null（只給遮罩值） */
  subject_id: string | null;
  subject_masked: string;
  level: number;
  remaining_seconds: number;
}

export interface ReleaseAbuseControlRequest {
  tenant_id: string;
  subject_kind: string;
  subject_id: string;
}
