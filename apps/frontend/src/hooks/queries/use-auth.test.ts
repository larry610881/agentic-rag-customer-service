import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useLogin } from "@/hooks/queries/use-auth";
import { useAuthStore } from "@/stores/use-auth-store";
import { AllProviders } from "@/test/test-utils";

describe("useLogin", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, tenantId: null, tenants: [] });
  });

  it("should login and set token on success", async () => {
    const { result } = renderHook(() => useLogin(), {
      wrapper: AllProviders,
    });

    result.current.mutate({ username: "admin", password: "password" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(useAuthStore.getState().token).toBe("mock-jwt-token-123");
  });
});
