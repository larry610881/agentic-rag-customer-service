import { KeyRound } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/use-auth-store";
import { ROUTES } from "@/routes/paths";

export function Header() {
  const logout = useAuthStore((s) => s.logout);
  const userId = useAuthStore((s) => s.userId);

  return (
    <header className="flex h-14 items-center justify-end gap-2 border-b border-primary/10 bg-background/60 backdrop-blur-md px-4">
      {userId && (
        <Button variant="ghost" size="sm" className="text-primary" asChild>
          <Link to={ROUTES.CHANGE_PASSWORD}>
            <KeyRound className="mr-1.5 h-4 w-4" />
            變更密碼
          </Link>
        </Button>
      )}
      <Button variant="outline" size="sm" className="text-primary" onClick={logout}>
        登出
      </Button>
    </header>
  );
}
