/**
 * Issue #75 — 防護階段三層設定（系統底線 / 方案 / 租戶 + bot 自選）。
 *
 * 對應後端 `interfaces/api/guard_settings_router.py` 與 `domain/security/guard_stages.py`；
 * 形狀假設全部集中在此，後端若調整只改這裡與 hooks。
 */

/** 防護階段識別字（`local_classifier` 為預留，前端顯示「即將推出」） */
export type GuardStage =
  | "regex_input"
  | "classifier_attack"
  | "output_guard"
  | "abuse_scoring"
  | "local_classifier";

/** 有效值的來源層；fallback = DB 失效時全開的 fail-safe */
export type GuardStageSource =
  | "required"
  | "platform"
  | "profile"
  | "tenant"
  | "bot"
  | "fallback";

export type GuardSourceMap = Record<string, GuardStageSource | string>;

/** 一層覆寫：只存有設定的鍵（platform: stages / required_stages；profile: stages；tenant: stages / locked / profile） */
export interface GuardOverrides {
  stages?: string[];
  required_stages?: string[];
  locked?: boolean;
  profile?: string;
}

/** 三層 resolve 後的有效防護（`EffectiveGuard.view()`） */
export interface GuardEffective {
  stages: string[];
  required: string[];
  locked: boolean;
  source_map: GuardSourceMap;
  /** 生效的方案名稱（未指定時為 standard） */
  profile: string;
}

/** GET /api/v1/admin/guard/settings（system_admin） */
export interface GuardSettingsOverview {
  platform_overrides: GuardOverrides;
  /** 內建（standard / exhibition）與 DB 方案；無 stages 鍵 = 沿用系統預設 */
  profiles: Record<string, GuardOverrides>;
  /** 平台層 + standard 方案的生效值（租戶未指定方案時的預設） */
  effective_default: GuardEffective;
  /** 全部可用階段（含預留） */
  stages: string[];
  /** 平台未設 required_stages 時的底線 */
  required_floor_default: string[];
  builtin_profiles: string[];
  allowed_keys: Record<string, string[]>;
}

/** GET / PUT /api/v1/admin/guard/settings/tenants/{tenant_id}（GET 供 tenant_admin 讀自己） */
export interface TenantGuardSettings {
  tenant_id: string;
  profile: string | null;
  overrides: GuardOverrides;
  locked: boolean;
  effective: GuardEffective;
  /** 只有 system_admin 為 true */
  editable: boolean;
}

/** GET /api/v1/guard/effective?bot_id=（租戶端；stages 已含 bot 加嚴，來源標 bot） */
export interface GuardEffectiveView extends GuardEffective {
  tenant_id: string;
  bot_id: string;
  /** bot 自設清單；null = 繼承 */
  bot_stages: string[] | null;
  /** 勾選清單的全集 */
  available_stages: string[];
}

/** PUT 回應 */
export interface GuardSettingsSaved {
  scope_kind: "platform" | "profile" | "tenant";
  scope_id: string;
  overrides: GuardOverrides;
  updated_at: string;
}

/** PUT platform / profiles/{name} */
export interface UpdateGuardOverridesRequest {
  overrides: GuardOverrides;
}

/** PUT tenants/{tenant_id} */
export interface UpdateTenantGuardRequest {
  profile?: string | null;
  overrides: GuardOverrides;
  locked?: boolean;
}
