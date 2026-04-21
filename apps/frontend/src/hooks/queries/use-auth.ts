import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import type {
  ChangePasswordRequest,
  LoginRequest,
  TokenResponse,
} from "@/types/auth";
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
      login(data.access_token, data.refresh_token);
    },
  });
}

export function useChangePassword() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (data: ChangePasswordRequest) =>
      apiFetch<void>(
        API_ENDPOINTS.auth.changePassword,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
  });
}
