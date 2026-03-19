import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { queryKeys } from "@/hooks/queries/keys";
import { useAuthStore } from "@/stores/use-auth-store";
import type { Tenant } from "@/types/auth";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

interface TenantConfigDialogProps {
  tenant: Tenant | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TenantConfigDialog({
  tenant,
  open,
  onOpenChange,
}: TenantConfigDialogProps) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState<string>("");
  const [agentModes, setAgentModes] = useState<string[]>([]);

  const mutation = useMutation({
    mutationFn: (data: { monthly_token_limit: number | null }) =>
      apiFetch<Tenant>(
        API_ENDPOINTS.tenants.config(tenant?.id ?? ""),
        {
          method: "PATCH",
          body: JSON.stringify(data),
        },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.all });
      onOpenChange(false);
    },
  });

  const agentModesMutation = useMutation({
    mutationFn: (data: { allowed_agent_modes: string[] }) =>
      apiFetch<Tenant>(
        API_ENDPOINTS.tenants.agentModes(tenant?.id ?? ""),
        {
          method: "PATCH",
          body: JSON.stringify(data),
        },
        token ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.all });
    },
  });

  const handleOpen = (isOpen: boolean) => {
    if (isOpen && tenant) {
      setLimit(tenant.monthly_token_limit?.toString() ?? "");
      setAgentModes(tenant.allowed_agent_modes ?? ["router"]);
    }
    onOpenChange(isOpen);
  };

  const handleSave = () => {
    const value = limit.trim() === "" ? null : parseInt(limit, 10);
    if (value !== null && isNaN(value)) return;
    mutation.mutate({ monthly_token_limit: value });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>租戶設定 — {tenant?.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="monthly-limit">每月 Token 上限</Label>
            <Input
              id="monthly-limit"
              type="number"
              placeholder="不限制（留空）"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              留空表示不限制。設定後可在 Token 用量頁面監控。
            </p>
          </div>
          <div className="space-y-2">
            <Label>Agent 模式權限</Label>
            {(["router", "react"] as const).map((mode) => (
              <div key={mode} className="flex items-center gap-3">
                <Switch
                  id={`agent-mode-${mode}`}
                  checked={agentModes.includes(mode)}
                  disabled={mode === "router" || agentModesMutation.isPending}
                  onCheckedChange={(checked) => {
                    const next = checked
                      ? [...agentModes, mode]
                      : agentModes.filter((m) => m !== mode);
                    setAgentModes(next);
                    agentModesMutation.mutate({ allowed_agent_modes: next });
                  }}
                />
                <span className="text-sm">
                  {mode === "router" ? "Router（預設）" : "ReAct"}
                </span>
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              控制該租戶可使用的 Agent 模式。Router 為預設，不可關閉。
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={mutation.isPending}>
            {mutation.isPending ? "儲存中..." : "儲存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
