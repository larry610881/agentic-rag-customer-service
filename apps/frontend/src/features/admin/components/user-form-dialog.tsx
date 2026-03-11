import { useState, useEffect } from "react";
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
  const { data: tenants } = useTenants();
  const realTenants = tenants?.filter((t) => t.id !== SYSTEM_TENANT_ID) ?? [];

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [tenantId, setTenantId] = useState("");

  useEffect(() => {
    if (open) {
      if (user) {
        setEmail(user.email);
        setPassword("");
        setRole(user.role);
        setTenantId(user.tenant_id);
      } else {
        setEmail("");
        setPassword("");
        setRole("user");
        setTenantId(realTenants[0]?.id ?? "");
      }
    }
  }, [open, user, realTenants]);

  useEffect(() => {
    if (role === "system_admin") {
      setTenantId(SYSTEM_TENANT_ID);
    } else if (tenantId === SYSTEM_TENANT_ID) {
      setTenantId(realTenants[0]?.id ?? "");
    }
  }, [role, tenantId, realTenants]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !role || !tenantId) return;
    if (!isEditing && !password) return;

    onSubmit({
      email,
      ...(isEditing ? {} : { password }),
      role,
      tenant_id: tenantId,
    });
  };

  const isSystemAdmin = role === "system_admin";

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
            <div className="space-y-2">
              <Label htmlFor="password">密碼</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label>角色</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="system_admin">系統管理員</SelectItem>
                <SelectItem value="tenant_admin">租戶管理員</SelectItem>
                <SelectItem value="user">一般使用者</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>租戶</Label>
            {isSystemAdmin ? (
              <Input value="系統租戶 (自動綁定)" disabled />
            ) : (
              <Select value={tenantId} onValueChange={setTenantId}>
                <SelectTrigger>
                  <SelectValue placeholder="選擇租戶" />
                </SelectTrigger>
                <SelectContent>
                  {realTenants.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

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
