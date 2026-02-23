import type { Tenant, TokenResponse } from "@/types/auth";

export const mockTokenResponse: TokenResponse = {
  access_token: "mock-jwt-token-123",
  token_type: "bearer",
};

export const mockTenants: Tenant[] = [
  {
    id: "tenant-1",
    name: "Acme Corp",
    slug: "acme-corp",
    created_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "tenant-2",
    name: "Beta Inc",
    slug: "beta-inc",
    created_at: "2024-02-01T00:00:00Z",
  },
];
