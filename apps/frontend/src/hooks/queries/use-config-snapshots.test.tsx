/** Issue #60 — config snapshot hooks 的 endpoint 契約測試（mock apiFetch） */

import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  useBotConfigTimeline,
  useConfigSnapshot,
  useConfigSnapshotDiff,
} from "@/hooks/queries/use-config-snapshots";
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

describe("use-config-snapshots", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    useAuthStore.setState({ token: "tok" });
  });

  it("useConfigSnapshot 打 GET /config-snapshots/{hash} 並帶 token", async () => {
    apiFetchMock.mockResolvedValue({ hash: "abc", snapshot: {} });
    const { result } = renderHook(() => useConfigSnapshot("abc123"), {
      wrapper: AllProviders,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/api/v1/config-snapshots/abc123",
      {},
      "tok",
    );
  });

  it("useConfigSnapshot 無 hash 時不打 API", () => {
    renderHook(() => useConfigSnapshot(null), { wrapper: AllProviders });
    expect(apiFetchMock).not.toHaveBeenCalled();
  });

  it("useConfigSnapshotDiff 打 GET /config-snapshots/diff?a=&b=", async () => {
    apiFetchMock.mockResolvedValue({ a: "h1", b: "h2", changed_fields: {} });
    const { result } = renderHook(() => useConfigSnapshotDiff("h1", "h2"), {
      wrapper: AllProviders,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/api/v1/config-snapshots/diff?a=h1&b=h2",
      {},
      "tok",
    );
  });

  it("useConfigSnapshotDiff enabled=false 時不打 API", () => {
    renderHook(() => useConfigSnapshotDiff("h1", "h2", false), {
      wrapper: AllProviders,
    });
    expect(apiFetchMock).not.toHaveBeenCalled();
  });

  it("useBotConfigTimeline 打 GET /bots/{id}/config-timeline?limit=", async () => {
    apiFetchMock.mockResolvedValue({ bot_id: "bot-1", items: [] });
    const { result } = renderHook(() => useBotConfigTimeline("bot-1", 20), {
      wrapper: AllProviders,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/api/v1/bots/bot-1/config-timeline?limit=20",
      {},
      "tok",
    );
  });
});
