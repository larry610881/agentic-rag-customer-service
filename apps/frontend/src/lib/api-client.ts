import { toast } from "sonner";

import { useAuthStore } from "@/stores/use-auth-store";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { API_BASE } from "@/lib/api-config";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${API_BASE}${API_ENDPOINTS.auth.refresh}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    useAuthStore.getState().login(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
  // M42：限制 401 後最多刷新+重試一次，避免「端點持續 401 但 refresh 持續成功」時
  // 無限遞迴請求風暴、Promise 永不 settle。
  _retried = false,
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    // L20：只有「帶 token 的已認證請求」的 401 才視為 session 過期；登入/refresh
    // 本身的 401（無 token）交由呼叫端自行顯示錯誤，不彈「登入已過期」toast。
    if (res.status === 401 && token) {
      if (!_retried) {
        // Deduplicate concurrent refresh attempts
        if (!refreshPromise) {
          refreshPromise = tryRefresh().finally(() => {
            refreshPromise = null;
          });
        }
        const refreshed = await refreshPromise;
        if (refreshed) {
          const newToken = useAuthStore.getState().token;
          return apiFetch(path, options, newToken ?? undefined, true);
        }
      }
      // refresh 失敗，或已重試一次仍 401 → session 確定過期
      toast.error("登入已過期，請重新登入", {
        description: "為確保帳號安全，閒置過久將自動登出",
      });
      useAuthStore.getState().logout();
    }
    const body = await res.text();
    if (res.status >= 500) {
      import("@/lib/error-reporter").then(({ errorReporter }) => {
        errorReporter.report({
          source: "frontend",
          error_type: `HTTP_${res.status}`,
          message: body,
          path: path,
          user_agent: navigator.userAgent,
        });
      });
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}
