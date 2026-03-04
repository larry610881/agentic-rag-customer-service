import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { LoginForm } from "@/features/auth/components/login-form";
import { useAuthStore } from "@/stores/use-auth-store";
import { ROUTES } from "@/routes/paths";

export default function LoginPage() {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);
  const navigate = useNavigate();

  useEffect(() => {
    if (token) {
      const dest = role === "system_admin" ? ROUTES.ADMIN_KNOWLEDGE_BASES : ROUTES.CHAT;
      navigate(dest, { replace: true });
    }
  }, [token, role, navigate]);

  if (token) {
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <LoginForm />
    </div>
  );
}
