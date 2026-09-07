/**
 * Issue #77 — 租戶「設定變更通知」偏好
 * GET/PUT /api/v1/tenants/{tenant_id}/notification-preferences（tenant_id 可為 "me"）
 */

/** 通知欄位群組鍵（後端 available_groups 的 key；前端不寫死清單，以後端回傳為準） */
export type ConfigChangeNotifyGroupKey =
  | "model"
  | "prompt"
  | "knowledge"
  | "tools"
  | "guard"
  | string;

export interface ConfigChangeNotifyGroup {
  key: ConfigChangeNotifyGroupKey;
  /** 顯示名稱（例：模型 / 提示詞 / 知識庫 / 工具 / 防護） */
  label: string;
}

export interface TenantNotificationPreferences {
  tenant_id: string;
  /** 租戶自訂的群組鍵；null = 沿用平台預設 */
  config_change_notify_fields: string[] | null;
  /** 目前生效的群組鍵（自訂或平台預設展開後） */
  effective_fields: string[];
  available_groups: ConfigChangeNotifyGroup[];
}

export interface UpdateTenantNotificationPreferencesRequest {
  /** 勾選的群組鍵陣列；null = 還原平台預設 */
  config_change_notify_fields: string[] | null;
}
