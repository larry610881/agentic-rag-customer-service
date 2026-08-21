import { describe, it, expect, vi, beforeEach } from "vitest";

import { apiFetch, ApiError } from "./api-client";
import { useAuthStore } from "@/stores/use-auth-store";

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

function jsonResponse(status: number, body: unknown = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

describe("apiFetch 401 handling (M42/L20)", () => {
  let logoutMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    logoutMock = vi.fn();
    useAuthStore.setState({
      token: "tok",
      refreshToken: "refresh",
      logout: logoutMock as unknown as () => void,
    });
  });

  it("已認證請求 401 → 刷新+重試一次成功", async () => {
    const fetchMock = vi
      .fn()
      // 原請求 401
      .mockResolvedValueOnce(jsonResponse(401))
      // refresh 成功
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "new", refresh_token: "r2" }),
      )
      // 重試成功
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const data = await apiFetch<{ ok: boolean }>("/x", {}, "tok");
    expect(data).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3); // 原 + refresh + 重試
  });

  it("持續 401（refresh 成功但重試仍 401）→ 只重試一次即登出，不無限迴圈", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401)) // 原請求
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "new", refresh_token: "r2" }),
      ) // refresh
      .mockResolvedValueOnce(jsonResponse(401)); // 重試仍 401
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/x", {}, "tok")).rejects.toBeInstanceOf(ApiError);
    // 原 + refresh + 重試 = 3，不再繼續
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(logoutMock).toHaveBeenCalled();
  });

  it("登入請求（無 token）401 → 不刷新、不登出、直接拋錯", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/auth/login", {})).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1); // 不嘗試 refresh
    expect(logoutMock).not.toHaveBeenCalled();
  });
});
