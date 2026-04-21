import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Tenant } from "@/types/auth";

function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const base64 = token.split(".")[1];
    const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return {};
  }
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  tenantId: string | null;
  role: string | null;
  /**
   * S-Auth.1: 只有 user_access JWT 才有 user_id（使用者層 token）；
   * tenant_access（dev mode）為 null — 因此可用來判斷「能否自助變更密碼」。
   */
  userId: string | null;
  tenants: Tenant[];
  login: (token: string, refreshToken: string) => void;
  logout: () => void;
  setTenantId: (tenantId: string) => void;
  setTenants: (tenants: Tenant[]) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      tenantId: null,
      role: null,
      userId: null,
      tenants: [],
      login: (token, refreshToken) => {
        const payload = decodeJwtPayload(token);
        const tokenType = payload.type as string | undefined;
        const sub = payload.sub as string | undefined;
        set({
          token,
          refreshToken,
          role: (payload.role as string) ?? null,
          tenantId: (payload.tenant_id as string) ?? null,
          userId: tokenType === "user_access" ? (sub ?? null) : null,
        });
      },
      logout: () =>
        set({
          token: null,
          refreshToken: null,
          tenantId: null,
          role: null,
          userId: null,
          tenants: [],
        }),
      setTenantId: (tenantId) => set({ tenantId }),
      setTenants: (tenants) => set({ tenants }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        tenantId: state.tenantId,
        role: state.role,
        userId: state.userId,
      }),
    },
  ),
);
