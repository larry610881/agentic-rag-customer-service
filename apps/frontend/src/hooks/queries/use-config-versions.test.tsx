import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useInvalidateVersionsOnGateComplete } from "./use-config-versions";
import { queryKeys } from "./keys";

function makeWrapper() {
  const queryClient = new QueryClient();
  const spy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper, spy };
}

describe("useInvalidateVersionsOnGateComplete (H18)", () => {
  it("gate run completed 時 invalidate 版本列表", () => {
    const { wrapper, spy } = makeWrapper();
    renderHook(
      () => useInvalidateVersionsOnGateComplete("bot-1", "completed"),
      { wrapper },
    );
    expect(spy).toHaveBeenCalledWith({
      queryKey: queryKeys.configVersions.list("bot-1"),
    });
  });

  it("gate run error 時也 invalidate", () => {
    const { wrapper, spy } = makeWrapper();
    renderHook(
      () => useInvalidateVersionsOnGateComplete("bot-1", "error"),
      { wrapper },
    );
    expect(spy).toHaveBeenCalledWith({
      queryKey: queryKeys.configVersions.list("bot-1"),
    });
  });

  it("running / undefined 不 invalidate（避免無謂刷新）", () => {
    const { wrapper, spy } = makeWrapper();
    const { rerender } = renderHook(
      ({ status }: { status: string | null }) =>
        useInvalidateVersionsOnGateComplete("bot-1", status),
      { wrapper, initialProps: { status: "running" as string | null } },
    );
    rerender({ status: null });
    expect(spy).not.toHaveBeenCalled();
  });
});
