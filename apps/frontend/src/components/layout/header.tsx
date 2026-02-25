"use client";

import { Button } from "@/components/ui/button";
import { TenantSelector } from "@/features/auth/components/tenant-selector";
import { useAuthStore } from "@/stores/use-auth-store";

export function Header() {
  const logout = useAuthStore((s) => s.logout);

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-4">
      <TenantSelector />
      <Button variant="ghost" size="sm" onClick={logout}>
        登出
      </Button>
    </header>
  );
}
