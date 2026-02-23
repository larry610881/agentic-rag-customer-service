export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}
