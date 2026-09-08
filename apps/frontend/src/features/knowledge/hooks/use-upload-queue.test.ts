import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiError } from "@/lib/api-client";
import { useUploadQueue } from "./use-upload-queue";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, getRateLimitSnapshot: () => ({ limit: null, remaining: null }) };
});

const makeFile = (name: string) =>
  new File(["x"], name, { type: "application/pdf" });

describe("useUploadQueue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("429 重試時沿用同一個 resume 物件（不會從第一步重跑）", async () => {
    const seen: Record<string, unknown>[] = [];
    let calls = 0;
    const task = vi.fn(async ({ resume }: { resume: Record<string, unknown> }) => {
      seen.push(resume);
      calls += 1;
      if (calls === 1) {
        // 模擬 confirm-upload 被限流：第一步已經做完，記在 resume 裡
        resume.documentId = "doc-1";
        throw new ApiError(429, "rate limited", 0);
      }
      return undefined;
    });

    const { result } = renderHook(() => useUploadQueue(task));
    act(() => {
      result.current.enqueue([{ id: "f1", file: makeFile("a.pdf") }]);
    });

    await waitFor(() => expect(result.current.stats.success).toBe(1));

    expect(calls).toBe(2);
    // 同一個物件 → 重試看得到第一次記下的 documentId
    expect(seen[0]).toBe(seen[1]);
    expect(seen[1].documentId).toBe("doc-1");
  });

  it("重試失敗會真的把工作放回佇列並重新送出", async () => {
    let calls = 0;
    const task = vi.fn(async () => {
      calls += 1;
      if (calls === 1) throw new Error("GCS upload network error");
      return undefined;
    });

    const { result } = renderHook(() => useUploadQueue(task));
    act(() => {
      result.current.enqueue([{ id: "f1", file: makeFile("a.pdf") }]);
    });
    await waitFor(() => expect(result.current.stats.error).toBe(1));

    act(() => {
      result.current.retryFailed();
    });
    await waitFor(() => expect(result.current.stats.success).toBe(1));
    expect(calls).toBe(2);
  });
});
