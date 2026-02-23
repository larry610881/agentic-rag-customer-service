import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useKnowledgeBases } from "@/hooks/queries/use-knowledge-bases";
import { useAuthStore } from "@/stores/use-auth-store";
import { AllProviders } from "@/test/test-utils";

describe("useKnowledgeBases", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("should fetch knowledge bases when authenticated with tenant", async () => {
    const { result } = renderHook(() => useKnowledgeBases(), {
      wrapper: AllProviders,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].name).toBe("Product Documentation");
  });

  it("should not fetch when no tenant selected", () => {
    useAuthStore.setState({ tenantId: null });
    const { result } = renderHook(() => useKnowledgeBases(), {
      wrapper: AllProviders,
    });
    expect(result.current.isFetching).toBe(false);
  });
});
