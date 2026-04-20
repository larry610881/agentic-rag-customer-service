export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Tenant {
  id: string;
  name: string;
  plan: string;
  monthly_token_limit: number | null;
  /** S-Token-Gov.2: NULL = 全部 category 計入；list = 只計入列表內的；[] = 全不計入 */
  included_categories: string[] | null;
  default_ocr_model: string;
  default_context_model: string;
  default_classification_model: string;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  account: string;
  password: string;
}
