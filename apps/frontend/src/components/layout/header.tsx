import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/use-auth-store";

export function Header() {
  const logout = useAuthStore((s) => s.logout);

  return (
    <header className="flex h-14 items-center justify-end border-b border-primary/10 bg-background/60 backdrop-blur-md px-4">
      <Button variant="outline" size="sm" className="text-primary" onClick={logout}>
        登出
      </Button>
    </header>
  );
}
