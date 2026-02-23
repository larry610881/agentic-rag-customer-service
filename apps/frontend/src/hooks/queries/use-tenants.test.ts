import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useTenants } from "@/hooks/queries/use-tenants";
import { useAuthStore } from "@/stores/use-auth-store";
import { AllProviders } from "@/test/test-utils";

describe("useTenants", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "test-token", tenantId: null, tenants: [] });
  });

  it("should fetch tenants when authenticated", async () => {
    const { result } = renderHook(() => useTenants(), {
      wrapper: AllProviders,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].name).toBe("Acme Corp");
  });

  it("should not fetch when no token", () => {
    useAuthStore.setState({ token: null });
    const { result } = renderHook(() => useTenants(), {
      wrapper: AllProviders,
    });
    expect(result.current.isFetching).toBe(false);
  });
});
