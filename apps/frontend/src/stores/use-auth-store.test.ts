import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAuthStore } from "@/stores/use-auth-store";
import { mockTenants } from "@/test/fixtures/auth";

const clearQueryCacheMock = vi.fn();
vi.mock("@/lib/query-client-registry", () => ({
  registerQueryClient: vi.fn(),
  clearQueryCache: () => clearQueryCacheMock(),
}));

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: null,
      tenantId: null,
      tenants: [],
    });
  });

  it("should have null initial state", () => {
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.tenantId).toBeNull();
    expect(state.tenants).toEqual([]);
  });

  it("should set token on login", () => {
    useAuthStore.getState().login("test-token", "test-refresh-token");
    expect(useAuthStore.getState().token).toBe("test-token");
  });

  it("should clear state on logout", () => {
    useAuthStore.getState().login("test-token", "test-refresh-token");
    useAuthStore.getState().setTenantId("tenant-1");
    useAuthStore.getState().setTenants(mockTenants);
    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.tenantId).toBeNull();
    expect(state.tenants).toEqual([]);
  });

  it("should clear the query cache on logout (M43 跨租戶快取隔離)", () => {
    clearQueryCacheMock.mockClear();
    useAuthStore.getState().login("test-token", "test-refresh-token");
    useAuthStore.getState().logout();
    expect(clearQueryCacheMock).toHaveBeenCalled();
  });

  it("should set tenantId", () => {
    useAuthStore.getState().setTenantId("tenant-1");
    expect(useAuthStore.getState().tenantId).toBe("tenant-1");
  });

  it("should set tenants", () => {
    useAuthStore.getState().setTenants(mockTenants);
    expect(useAuthStore.getState().tenants).toEqual(mockTenants);
  });
});
