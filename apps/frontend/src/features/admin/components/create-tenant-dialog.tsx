import { useState } from "react";
import { useCreateTenant } from "@/hooks/queries/use-tenants";
import { toast } from "sonner";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PLAN_OPTIONS = [
  { value: "starter", label: "Starter" },
  { value: "pro", label: "Pro" },
  { value: "enterprise", label: "Enterprise" },
  { value: "system", label: "System" },
] as const;

interface CreateTenantDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateTenantDialog({
  open,
  onOpenChange,
}: CreateTenantDialogProps) {
  const [name, setName] = useState("");
  const [plan, setPlan] = useState("starter");
  const mutation = useCreateTenant();

  const handleOpen = (isOpen: boolean) => {
    if (isOpen) {
      setName("");
      setPlan("starter");
    }
    onOpenChange(isOpen);
  };

  const handleSubmit = () => {
    const trimmed = name.trim();
    if (!trimmed) return;

    mutation.mutate(
      { name: trimmed, plan },
      {
        onSuccess: () => {
          toast.success("租戶建立成功");
          handleOpen(false);
        },
        onError: () => {
          toast.error("租戶建立失敗");
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>建立租戶</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="tenant-name">租戶名稱</Label>
            <Input
              id="tenant-name"
              placeholder="輸入租戶名稱"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tenant-plan">方案</Label>
            <Select value={plan} onValueChange={setPlan}>
              <SelectTrigger id="tenant-plan">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PLAN_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpen(false)}>
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!name.trim() || mutation.isPending}
          >
            {mutation.isPending ? "建立中..." : "建立"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
