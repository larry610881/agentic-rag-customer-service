import { Suspense, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { useAuthStore } from "@/stores/use-auth-store";
import { useTenants } from "@/hooks/queries/use-tenants";

function useSyncTenants() {
  const { data } = useTenants();
  const tenants = data?.items;
  const setTenants = useAuthStore((s) => s.setTenants);
  const tenantId = useAuthStore((s) => s.tenantId);
  const setTenantId = useAuthStore((s) => s.setTenantId);

  useEffect(() => {
    if (tenants && tenants.length > 0) {
      setTenants(tenants);
      if (!tenantId) {
        setTenantId(tenants[0].id);
      }
    }
  }, [tenants, tenantId, setTenantId, setTenants]);
}

export function AppShell() {
  useSyncTenants();

  return (
    <div className="relative flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto">
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center">
                <p className="text-muted-foreground">載入中...</p>
              </div>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
