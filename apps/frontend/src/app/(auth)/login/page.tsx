"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoginForm } from "@/features/auth/components/login-form";
import { useAuthStore } from "@/stores/use-auth-store";

export default function LoginPage() {
  const token = useAuthStore((s) => s.token);
  const router = useRouter();

  useEffect(() => {
    if (token) {
      router.replace("/chat");
    }
  }, [token, router]);

  if (token) {
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <LoginForm />
    </div>
  );
}
