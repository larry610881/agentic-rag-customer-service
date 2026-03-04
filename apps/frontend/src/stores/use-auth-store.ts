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
  tenantId: string | null;
  role: string | null;
  tenants: Tenant[];
  login: (token: string) => void;
  logout: () => void;
  setTenantId: (tenantId: string) => void;
  setTenants: (tenants: Tenant[]) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      tenantId: null,
      role: null,
      tenants: [],
      login: (token) => {
        const payload = decodeJwtPayload(token);
        set({
          token,
          role: (payload.role as string) ?? null,
          tenantId: (payload.tenant_id as string) ?? null,
        });
      },
      logout: () => set({ token: null, tenantId: null, role: null, tenants: [] }),
      setTenantId: (tenantId) => set({ tenantId }),
      setTenants: (tenants) => set({ tenants }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        token: state.token,
        tenantId: state.tenantId,
        role: state.role,
      }),
    },
  ),
);
