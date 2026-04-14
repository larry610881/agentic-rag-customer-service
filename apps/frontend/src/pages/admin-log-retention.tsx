import { useState } from "react";
import {
  useLogRetentionPolicy,
  useUpdateLogRetentionPolicy,
  useExecuteLogCleanup,
} from "@/hooks/queries/use-log-retention";
import { formatDateTime } from "@/lib/format-date";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, i) => i);

const INTERVAL_OPTIONS = [
  { label: "每天 1 次", value: "24" },
  { label: "每天 2 次", value: "12" },
  { label: "每天 4 次", value: "6" },
];

function formatDatetime(iso: string | null): string {
  if (!iso) return "--";
  return formatDateTime(iso);
}

export default function AdminLogRetentionPage() {
  const { data, isLoading } = useLogRetentionPolicy();
  const updateMutation = useUpdateLogRetentionPolicy();
  const cleanupMutation = useExecuteLogCleanup();

  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [retentionDays, setRetentionDays] = useState<number | null>(null);
  const [cleanupHour, setCleanupHour] = useState<string | null>(null);
  const [intervalHours, setIntervalHours] = useState<string | null>(null);

  const effectiveEnabled = enabled ?? data?.enabled ?? false;
  const effectiveRetentionDays = retentionDays ?? data?.retention_days ?? 30;
  const effectiveCleanupHour = cleanupHour ?? String(data?.cleanup_hour ?? 3);
  const effectiveIntervalHours =
    intervalHours ?? String(data?.cleanup_interval_hours ?? 24);

  const isDirty =
    data != null &&
    (effectiveEnabled !== data.enabled ||
      effectiveRetentionDays !== data.retention_days ||
      Number(effectiveCleanupHour) !== data.cleanup_hour ||
      Number(effectiveIntervalHours) !== data.cleanup_interval_hours);

  const handleSave = () => {
    updateMutation.mutate(
      {
        enabled: effectiveEnabled,
        retention_days: effectiveRetentionDays,
        cleanup_hour: Number(effectiveCleanupHour),
        cleanup_interval_hours: Number(effectiveIntervalHours),
      },
      {
        onSuccess: () => {
          toast.success("日誌清理策略已更新");
          setEnabled(null);
          setRetentionDays(null);
          setCleanupHour(null);
          setIntervalHours(null);
        },
        onError: () => toast.error("儲存失敗"),
      },
    );
  };

  const handleCleanup = () => {
    cleanupMutation.mutate(undefined, {
      onSuccess: (result) => {
        toast.success(`清理完成，已刪除 ${result.deleted_count} 筆日誌`);
      },
      onError: () => toast.error("清理執行失敗"),
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">日誌清理策略</h1>
          <p className="text-muted-foreground">管理系統日誌自動清理排程</p>
        </div>
        <p className="text-muted-foreground">載入中...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">日誌清理策略</h1>
        <p className="text-muted-foreground">管理系統日誌自動清理排程</p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>清理設定</CardTitle>
          <CardDescription>
            設定日誌自動清理的排程與保留期限
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <Label htmlFor="enabled">啟用自動清理</Label>
            <Switch
              id="enabled"
              checked={effectiveEnabled}
              onCheckedChange={(v) => setEnabled(v)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="retention-days">保留天數</Label>
            <Input
              id="retention-days"
              type="number"
              min={1}
              className="w-32"
              value={effectiveRetentionDays}
              onChange={(e) => setRetentionDays(Number(e.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="cleanup-hour">執行時間（時）</Label>
            <Select
              value={effectiveCleanupHour}
              onValueChange={setCleanupHour}
            >
              <SelectTrigger id="cleanup-hour" className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HOUR_OPTIONS.map((h) => (
                  <SelectItem key={h} value={String(h)}>
                    {String(h).padStart(2, "0")}:00
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="interval">執行頻率</Label>
            <Select
              value={effectiveIntervalHours}
              onValueChange={setIntervalHours}
            >
              <SelectTrigger id="interval" className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INTERVAL_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1 text-sm text-muted-foreground">
            <p>上次執行：{formatDatetime(data?.last_cleanup_at ?? null)}</p>
            <p>上次刪除筆數：{data?.deleted_count_last ?? "--"}</p>
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              onClick={handleSave}
              disabled={!isDirty || updateMutation.isPending}
            >
              {updateMutation.isPending ? "儲存中..." : "儲存"}
            </Button>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" disabled={cleanupMutation.isPending}>
                  {cleanupMutation.isPending ? "清理中..." : "立即清理"}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>確認立即清理</AlertDialogTitle>
                  <AlertDialogDescription>
                    這將立即刪除超過保留天數的日誌記錄，此操作無法復原。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={handleCleanup}>
                    確認清理
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
