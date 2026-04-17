import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTenants } from "@/hooks/queries/use-tenants";
import {
  useUpdateToolScope,
  type AdminTool,
} from "@/hooks/queries/use-admin-tools";

type ToolScopeDialogProps = {
  tool: AdminTool | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export const ToolScopeDialog = ({
  tool,
  open,
  onOpenChange,
}: ToolScopeDialogProps) => {
  const { data: tenantsData, isLoading: tenantsLoading } = useTenants(1, 100);
  const updateMutation = useUpdateToolScope();

  const [scope, setScope] = useState<"global" | "tenant">("global");
  const [selectedTenants, setSelectedTenants] = useState<string[]>([]);

  useEffect(() => {
    if (tool && open) {
      setScope(tool.scope);
      setSelectedTenants([...tool.tenant_ids]);
    }
  }, [tool, open]);

  if (!tool) return null;

  const handleToggleTenant = (tenantId: string, checked: boolean) => {
    setSelectedTenants((prev) =>
      checked ? [...prev, tenantId] : prev.filter((id) => id !== tenantId),
    );
  };

  const handleSubmit = () => {
    if (scope === "tenant" && selectedTenants.length === 0) {
      toast.error("請至少選擇一個租戶作為白名單");
      return;
    }
    updateMutation.mutate(
      {
        name: tool.name,
        payload: {
          scope,
          tenant_ids: scope === "tenant" ? selectedTenants : [],
        },
      },
      {
        onSuccess: () => {
          toast.success(`已更新「${tool.label}」的可見範圍`);
          onOpenChange(false);
        },
        onError: (err) => {
          toast.error(
            err instanceof Error ? err.message : "更新失敗，請稍後再試",
          );
        },
      },
    );
  };

  const tenants = tenantsData?.items ?? [];
  const submitting = updateMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>設定工具可見範圍</DialogTitle>
          <DialogDescription>
            「{tool.label}」（{tool.name}）
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="scope-select">Scope</Label>
            <Select
              value={scope}
              onValueChange={(v) => setScope(v as "global" | "tenant")}
            >
              <SelectTrigger id="scope-select">
                <SelectValue placeholder="選擇 scope" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="global">
                  Global — 所有租戶可見
                </SelectItem>
                <SelectItem value="tenant">
                  Tenant — 僅白名單租戶可見
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {scope === "tenant" && (
            <div className="flex flex-col gap-2">
              <Label>白名單租戶</Label>
              {tenantsLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  載入租戶清單...
                </div>
              ) : tenants.length === 0 ? (
                <p className="text-sm text-muted-foreground">尚無任何租戶</p>
              ) : (
                <ScrollArea className="h-48 rounded border p-2">
                  <div className="flex flex-col gap-2">
                    {tenants.map((tenant) => (
                      <div
                        key={tenant.id}
                        className="flex items-center gap-2"
                      >
                        <Checkbox
                          id={`tenant-${tenant.id}`}
                          checked={selectedTenants.includes(tenant.id)}
                          onCheckedChange={(checked) =>
                            handleToggleTenant(tenant.id, !!checked)
                          }
                        />
                        <Label
                          htmlFor={`tenant-${tenant.id}`}
                          className="font-normal"
                        >
                          {tenant.name}
                        </Label>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
              <p className="text-xs text-muted-foreground">
                已選 {selectedTenants.length} / {tenants.length} 個租戶
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            儲存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
