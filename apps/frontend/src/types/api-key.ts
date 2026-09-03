/** Issue #67 P2 — 租戶 API 金鑰（client_credentials） */

export interface ApiKey {
  id: string;
  /** 與 id 相同，作為 OAuth client_credentials 的 client_id */
  client_id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  /** secret 前綴，供辨識用；完整 secret 只在建立時回傳一次 */
  secret_prefix: string;
  scopes: string[];
  /** 空陣列 = 全部機器人 */
  allowed_bot_ids: string[];
  expires_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
  last_used_at: string | null;
  created_by: string | null;
  created_at: string;
}

/** POST /api/v1/api-keys 回應：多一個只顯示一次的 client_secret */
export interface ApiKeyCreated extends ApiKey {
  client_secret: string;
}

export interface CreateApiKeyRequest {
  name: string;
  description?: string;
  scopes: string[];
  allowed_bot_ids?: string[];
  expires_at?: string | null;
  /** system_admin 必填；tenant_admin 不可指定 */
  tenant_id?: string;
}

export type ApiKeyStatus = "active" | "revoked" | "expired";

export function getApiKeyStatus(key: ApiKey, now: Date = new Date()): ApiKeyStatus {
  if (key.revoked_at) return "revoked";
  if (key.expires_at && new Date(key.expires_at).getTime() <= now.getTime()) {
    return "expired";
  }
  return key.is_active ? "active" : "revoked";
}

export const API_KEY_STATUS_LABELS: Record<ApiKeyStatus, string> = {
  active: "使用中",
  revoked: "已撤銷",
  expired: "已過期",
};

/** 後端固定 scope 清單的中文說明；未列出的 scope 直接顯示原字串 */
export const API_KEY_SCOPE_LABELS: Record<string, string> = {
  "chat:send": "非串流聊天",
  "chat:stream": "串流聊天",
  "chat:history:read": "讀取對話紀錄",
  "feedback:write": "送出回饋",
  "bots:read": "讀取機器人",
  "kb:read": "保留（尚未實作）",
  "kb:write": "保留（尚未實作）",
};
