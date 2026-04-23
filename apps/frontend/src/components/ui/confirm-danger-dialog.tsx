import { useEffect, useState } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ConfirmDangerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** 必須輸入此名稱才能 enable confirm 按鈕 */
  confirmName?: string;
  confirmLabel?: string;
  isPending?: boolean;
  onConfirm: () => void | Promise<void>;
}

export function ConfirmDangerDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmName,
  confirmLabel = "確認刪除",
  isPending = false,
  onConfirm,
}: ConfirmDangerDialogProps) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const isConfirmEnabled =
    !confirmName || typed.trim() === confirmName.trim();

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>

        {confirmName && (
          <div className="space-y-2 py-2">
            <Label htmlFor="confirm-name-input">
              請輸入「<span className="font-mono font-bold">{confirmName}</span>」確認
            </Label>
            <Input
              id="confirm-name-input"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={confirmName}
              autoComplete="off"
            />
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault();
              if (isConfirmEnabled && !isPending) onConfirm();
            }}
            disabled={!isConfirmEnabled || isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isPending ? "處理中..." : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
