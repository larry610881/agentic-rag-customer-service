import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Tenant } from "@/types/auth";

interface AuthState {
  token: string | null;
  tenantId: string | null;
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
      tenants: [],
      login: (token) => set({ token }),
      logout: () => set({ token: null, tenantId: null, tenants: [] }),
      setTenantId: (tenantId) => set({ tenantId }),
      setTenants: (tenants) => set({ tenants }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        token: state.token,
        tenantId: state.tenantId,
      }),
    },
  ),
);
