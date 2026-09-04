/** Issue #68 P7b — Widget 宿主身分綁定（identity secret）後台設定 */

export interface WidgetIdentityStatus {
  tenant_id: string;
  /** 是否已產生過 secret；為 false 時 is_enabled / enforce_verified 無法變更 */
  has_secret: boolean;
  is_enabled: boolean;
  /** 開啟後簽章錯誤的 identify 直接回 403；關閉時失敗只降級為匿名並計分 */
  enforce_verified: boolean;
  /** ISO 8601；尚未產生 secret 時為 null */
  rotated_at: string | null;
}

/** 輪替回應：secret 只回傳這一次 */
export interface WidgetIdentityRotated {
  tenant_id: string;
  secret: string;
}

/** PUT 只送有變更的欄位 */
export interface UpdateWidgetIdentityPolicyRequest {
  is_enabled?: boolean;
  enforce_verified?: boolean;
}
