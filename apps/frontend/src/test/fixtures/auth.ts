import type { Tenant, TokenResponse } from "@/types/auth";

export const mockTokenResponse: TokenResponse = {
  access_token: "mock-jwt-token-123",
  refresh_token: "mock-refresh-token-456",
  token_type: "bearer",
};

export const mockTenants: Tenant[] = [
  {
    id: "tenant-1",
    name: "Acme Corp",
    plan: "pro",
    allowed_agent_modes: ["router", "react"],
    allowed_widget_avatar: false,
    monthly_token_limit: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "tenant-2",
    name: "Beta Inc",
    plan: "starter",
    allowed_agent_modes: ["router"],
    allowed_widget_avatar: false,
    monthly_token_limit: null,
    created_at: "2024-02-01T00:00:00Z",
    updated_at: "2024-02-01T00:00:00Z",
  },
];
