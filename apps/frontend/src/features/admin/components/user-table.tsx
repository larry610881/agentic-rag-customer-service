import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { UserFormDialog } from "@/features/admin/components/user-form-dialog";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import {
  useAdminUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  useResetPassword,
} from "@/hooks/queries/use-admin-users";
import type { User } from "@/types/user";

const ROLE_LABELS: Record<string, string> = {
  system_admin: "系統管理員",
  tenant_admin: "租戶管理員",
  user: "一般使用者",
};

export function UserTable() {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const { data: users, isLoading, isError } = useAdminUsers(tenantId);
  const tenantNameMap = useTenantNameMap();

  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();
  const resetPassword = useResetPassword();

  const [formOpen, setFormOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | undefined>();
  const [deleteTarget, setDeleteTarget] = useState<User | undefined>();
  const [resetTarget, setResetTarget] = useState<User | undefined>();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const handleCreate = () => {
    setEditingUser(undefined);
    setFormOpen(true);
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setFormOpen(true);
  };

  const handleFormSubmit = (data: {
    email: string;
    password?: string;
    role: string;
    tenant_id: string;
  }) => {
    if (editingUser) {
      updateUser.mutate(
        {
          userId: editingUser.id,
          data: { role: data.role, tenant_id: data.tenant_id },
        },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createUser.mutate(
        {
          email: data.email,
          password: data.password!,
          role: data.role,
          tenant_id: data.tenant_id,
        },
        { onSuccess: () => setFormOpen(false) },
      );
    }
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteUser.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(undefined),
    });
  };

  const handleResetPassword = () => {
    if (!resetTarget || !newPassword || newPassword !== confirmPassword) return;
    resetPassword.mutate(
      { userId: resetTarget.id, data: { new_password: newPassword } },
      {
        onSuccess: () => {
          setResetTarget(undefined);
          setNewPassword("");
          setConfirmPassword("");
        },
      },
    );
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <AdminTenantFilter value={tenantId} onChange={setTenantId} />
        </div>
        <Button onClick={handleCreate}>新增帳號</Button>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded" />
          ))}
        </div>
      )}

      {isError && <p className="text-destructive">載入帳號失敗。</p>}

      {users && users.length === 0 && (
        <p className="text-muted-foreground">目前沒有任何帳號。</p>
      )}

      {users && users.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>租戶</TableHead>
                <TableHead>建立時間</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.email}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        user.role === "system_admin"
                          ? "default"
                          : user.role === "tenant_admin"
                            ? "secondary"
                            : "outline"
                      }
                    >
                      {ROLE_LABELS[user.role] ?? user.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {tenantNameMap.get(user.tenant_id) ??
                      user.tenant_id.slice(0, 8)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString("zh-TW")}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEdit(user)}
                      >
                        編輯
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setResetTarget(user);
                          setNewPassword("");
                          setConfirmPassword("");
                        }}
                      >
                        重設密碼
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(user)}
                      >
                        刪除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <UserFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        user={editingUser}
        onSubmit={handleFormSubmit}
        isPending={createUser.isPending || updateUser.isPending}
      />

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(undefined)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>確認刪除帳號</AlertDialogTitle>
            <AlertDialogDescription>
              確定要刪除 {deleteTarget?.email} 嗎？此操作無法復原。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteUser.isPending}
            >
              {deleteUser.isPending ? "刪除中..." : "刪除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={!!resetTarget}
        onOpenChange={(open) => {
          if (!open) {
            setResetTarget(undefined);
            setNewPassword("");
            setConfirmPassword("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>重設密碼 - {resetTarget?.email}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">新密碼</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={6}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">確認密碼</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                minLength={6}
              />
            </div>
            {newPassword &&
              confirmPassword &&
              newPassword !== confirmPassword && (
                <p className="text-sm text-destructive">密碼不一致</p>
              )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResetTarget(undefined)}
            >
              取消
            </Button>
            <Button
              onClick={handleResetPassword}
              disabled={
                resetPassword.isPending ||
                !newPassword ||
                newPassword !== confirmPassword
              }
            >
              {resetPassword.isPending ? "重設中..." : "確認重設"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
