/** Issue #60 — audit log hook 的 endpoint 契約測試（mock apiFetch） */

import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuditLogs } from "@/hooks/queries/use-audit-logs";
import { useAuthStore } from "@/stores/use-auth-store";
import { AllProviders } from "@/test/test-utils";

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

import { apiFetch } from "@/lib/api-client";
const apiFetchMock = vi.mocked(apiFetch);

describe("useAuditLogs", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    useAuthStore.setState({ token: "tok" });
  });

  it("依 filters 組 query string（略過空值）", async () => {
    apiFetchMock.mockResolvedValue({ items: [], limit: 20, offset: 40 });
    const { result } = renderHook(
      () =>
        useAuditLogs({
          tenant_id: "t-1",
          entity_type: "bot",
          entity_id: undefined,
          limit: 20,
          offset: 40,
        }),
      { wrapper: AllProviders },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/api/v1/audit-logs?tenant_id=t-1&entity_type=bot&limit=20&offset=40",
      {},
      "tok",
    );
  });

  it("未登入時不打 API", () => {
    useAuthStore.setState({ token: null });
    renderHook(() => useAuditLogs({ limit: 20, offset: 0 }), {
      wrapper: AllProviders,
    });
    expect(apiFetchMock).not.toHaveBeenCalled();
  });
});
