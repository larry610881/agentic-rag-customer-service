export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Tenant {
  id: string;
  name: string;
  plan: string;
  allowed_agent_modes: string[];
  allowed_widget_avatar: boolean;
  monthly_token_limit: number | null;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  account: string;
  password: string;
}
