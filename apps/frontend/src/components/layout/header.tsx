import { Button } from "@/components/ui/button";
import { TenantSelector } from "@/features/auth/components/tenant-selector";
import { useAuthStore } from "@/stores/use-auth-store";

export function Header() {
  const logout = useAuthStore((s) => s.logout);
  const role = useAuthStore((s) => s.role);

  return (
    <header className="flex h-14 items-center justify-between border-b border-primary/10 bg-background/60 backdrop-blur-md px-4">
      {role === "system_admin" ? <TenantSelector /> : <div />}
      <Button variant="outline" size="sm" className="text-primary" onClick={logout}>
        登出
      </Button>
    </header>
  );
}
