import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import type { LoginRequest, TokenResponse } from "@/types/auth";
import { useAuthStore } from "@/stores/use-auth-store";

export function useLogin() {
  const login = useAuthStore((s) => s.login);

  return useMutation({
    mutationFn: (data: LoginRequest) =>
      apiFetch<TokenResponse>(API_ENDPOINTS.auth.login, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: (data) => {
      login(data.access_token);
    },
  });
}
