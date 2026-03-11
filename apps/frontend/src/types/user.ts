export interface User {
  id: string;
  tenant_id: string;
  email: string;
  role: "system_admin" | "tenant_admin" | "user";
  created_at: string;
  updated_at: string;
}

export interface CreateUserRequest {
  email: string;
  password: string;
  role: string;
  tenant_id: string;
}

export interface UpdateUserRequest {
  role?: string;
  tenant_id?: string;
}

export interface ResetPasswordRequest {
  new_password: string;
}
