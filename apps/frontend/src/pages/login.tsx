import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { LoginForm } from "@/features/auth/components/login-form";
import { useAuthStore } from "@/stores/use-auth-store";
import { ROUTES } from "@/routes/paths";

export default function LoginPage() {
  const token = useAuthStore((s) => s.token);
  const navigate = useNavigate();

  useEffect(() => {
    if (token) {
      navigate(ROUTES.CHAT, { replace: true });
    }
  }, [token, navigate]);

  if (token) {
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center mb-8 absolute top-12">
        <h1 className="text-4xl font-heading font-bold tracking-widest text-primary">RAG 客服系統</h1>
        <p className="text-muted-foreground mt-2 text-sm tracking-wider">智能客服平台</p>
      </div>
      <LoginForm />
    </div>
  );
}
