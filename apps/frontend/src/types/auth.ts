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
