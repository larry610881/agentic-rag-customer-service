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
    if (res.status === 401) {
      // Deduplicate concurrent refresh attempts
      if (!refreshPromise) {
        refreshPromise = tryRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const refreshed = await refreshPromise;
      if (refreshed) {
        const newToken = useAuthStore.getState().token;
        return apiFetch(path, options, newToken ?? undefined);
      }
      toast.error("登入已過期，請重新登入", {
        description: "為確保帳號安全，閒置過久將自動登出",
      });
      useAuthStore.getState().logout();
    }
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}
