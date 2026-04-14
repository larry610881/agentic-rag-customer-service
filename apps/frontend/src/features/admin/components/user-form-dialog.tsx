import { useState, useEffect, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTenants } from "@/hooks/queries/use-tenants";
import type { User } from "@/types/user";

const SYSTEM_TENANT_ID = "00000000-0000-0000-0000-000000000000";

interface UserFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user?: User;
  onSubmit: (data: {
    email: string;
    password?: string;
    role: string;
    tenant_id: string;
  }) => void;
  isPending: boolean;
}

export function UserFormDialog({
  open,
  onOpenChange,
  user,
  onSubmit,
  isPending,
}: UserFormDialogProps) {
  const isEditing = !!user;
  const { data: tenantsData } = useTenants();
  const realTenants =
    tenantsData?.items?.filter((t) => t.id !== SYSTEM_TENANT_ID) ?? [];

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [role, setRole] = useState("tenant_admin");
  const [tenantId, setTenantId] = useState("");

  // Only reset form when dialog opens, not on every realTenants change
  const initializedRef = useRef(false);
  useEffect(() => {
    if (open) {
      if (user) {
        setEmail(user.email);
        setPassword("");
        setConfirmPassword("");
        setPasswordError("");
        setRole(user.role);
        setTenantId(user.tenant_id);
      } else if (!initializedRef.current) {
        setEmail("");
        setPassword("");
        setConfirmPassword("");
        setPasswordError("");
        setRole("tenant_admin");
        setTenantId(realTenants[0]?.id ?? "");
      }
      initializedRef.current = true;
    } else {
      initializedRef.current = false;
    }
  }, [open, user]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-set tenant when role changes
  useEffect(() => {
    if (role === "system_admin") {
      setTenantId(SYSTEM_TENANT_ID);
    } else if (tenantId === SYSTEM_TENANT_ID || !tenantId) {
      setTenantId(realTenants[0]?.id ?? "");
    }
  }, [role]); // eslint-disable-line react-hooks/exhaustive-deps

  const isTenantRole = role === "tenant_admin";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !role || !tenantId) return;

    if (!isEditing) {
      if (!password) return;
      if (password !== confirmPassword) {
        setPasswordError("密碼不一致");
        return;
      }
      setPasswordError("");
    }

    onSubmit({
      email,
      ...(isEditing ? {} : { password }),
      role,
      tenant_id: tenantId,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEditing ? "編輯帳號" : "新增帳號"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isEditing}
              required
            />
          </div>

          {!isEditing && (
            <>
              <div className="space-y-2">
                <Label htmlFor="password">密碼</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setPasswordError("");
                  }}
                  required
                  minLength={6}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password">確認密碼</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    setPasswordError("");
                  }}
                  required
                  minLength={6}
                />
                {passwordError && (
                  <p className="text-xs text-destructive">{passwordError}</p>
                )}
              </div>
            </>
          )}

          <div className="space-y-2">
            <Label>角色</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent position="popper" sideOffset={4}>
                <SelectItem value="system_admin">系統管理員</SelectItem>
                <SelectItem value="tenant_admin">租戶管理員</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isTenantRole && (
            <div className="space-y-2">
              <Label>租戶</Label>
              <Select value={tenantId} onValueChange={setTenantId}>
                <SelectTrigger>
                  <SelectValue placeholder="選擇租戶" />
                </SelectTrigger>
                <SelectContent position="popper" sideOffset={4}>
                  {realTenants.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "處理中..." : isEditing ? "儲存" : "建立"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
