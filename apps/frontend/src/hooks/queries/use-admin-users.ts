import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type {
  User,
  CreateUserRequest,
  UpdateUserRequest,
  ResetPasswordRequest,
} from "@/types/user";

export function useAdminUsers(tenantId?: string) {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  const url = tenantId
    ? `${API_ENDPOINTS.adminUsers.list}?tenant_id=${tenantId}`
    : API_ENDPOINTS.adminUsers.list;

  return useQuery({
    queryKey: queryKeys.admin.users(tenantId),
    queryFn: () => apiFetch<User[]>(url, {}, token ?? undefined),
    enabled: !!token && role === "system_admin",
  });
}

export function useCreateUser() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateUserRequest) =>
      apiFetch<User>(
        API_ENDPOINTS.adminUsers.create,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("帳號建立成功");
      queryClient.invalidateQueries({
        queryKey: ["admin", "users"],
      });
    },
    onError: () => {
      toast.error("建立帳號失敗");
    },
  });
}

export function useUpdateUser() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: UpdateUserRequest }) =>
      apiFetch<User>(
        API_ENDPOINTS.adminUsers.update(userId),
        { method: "PUT", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("帳號更新成功");
      queryClient.invalidateQueries({
        queryKey: ["admin", "users"],
      });
    },
    onError: () => {
      toast.error("更新帳號失敗");
    },
  });
}

export function useDeleteUser() {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch<void>(
        API_ENDPOINTS.adminUsers.delete(userId),
        { method: "DELETE" },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("帳號已刪除");
      queryClient.invalidateQueries({
        queryKey: ["admin", "users"],
      });
    },
    onError: () => {
      toast.error("刪除帳號失敗");
    },
  });
}

export function useResetPassword() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: ResetPasswordRequest }) =>
      apiFetch<void>(
        API_ENDPOINTS.adminUsers.resetPassword(userId),
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
    onSuccess: () => {
      toast.success("密碼重設成功");
    },
    onError: () => {
      toast.error("密碼重設失敗");
    },
  });
}
