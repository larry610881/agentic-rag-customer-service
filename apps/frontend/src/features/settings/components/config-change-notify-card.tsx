import { useEffect, useMemo, useState } from "react";
import { BellRing } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  useTenantNotificationPreferences,
  useUpdateTenantNotificationPreferences,
} from "@/hooks/queries/use-notification-preferences";

interface ConfigChangeNotifyCardProps {
  tenantId: string | null;
}

function sameSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const s = new Set(a);
  return b.every((k) => s.has(k));
}

/**
 * Issue #77 — 租戶設定頁「設定變更通知」：勾選哪些欄位群組被修改時要通知渠道。
 * 儲存送勾選陣列；「還原平台預設」送 null（後端改以平台預設展開 effective_fields）。
 */
export function ConfigChangeNotifyCard({ tenantId }: ConfigChangeNotifyCardProps) {
  const prefs = useTenantNotificationPreferences(tenantId);
  const update = useUpdateTenantNotificationPreferences(tenantId);
  const data = prefs.data;

  // 勾選以後端展開的生效值為準（自訂或平台預設）
  const serverSelected = useMemo(() => data?.effective_fields ?? [], [data]);
  const [selected, setSelected] = useState<string[]>(serverSelected);

  useEffect(() => {
    setSelected(serverSelected);
  }, [serverSelected]);

  const usingDefault = data?.config_change_notify_fields === null;
  const dirty = data ? !sameSet(selected, serverSelected) : false;

  const toggle = (key: string, checked: boolean) => {
    setSelected((prev) =>
      checked ? (prev.includes(key) ? prev : [...prev, key]) : prev.filter((k) => k !== key),
    );
  };

  const save = (fields: string[] | null) => {
    update.mutate(
      { config_change_notify_fields: fields },
      {
        onSuccess: () =>
          toast.success(fields === null ? "已還原平台預設" : "設定變更通知已儲存"),
        onError: () => toast.error("儲存失敗"),
      },
    );
  };

  return (
    <Card data-testid="config-change-notify-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BellRing className="h-4 w-4" />
          設定變更通知
          {data && (
            <Badge variant={usingDefault ? "secondary" : "outline"}>
              {usingDefault ? "平台預設" : "租戶自訂"}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          勾選的設定被修改時，會透過已開啟「設定變更通知」的通知渠道發送。系統管理員對本租戶的變更也會通知。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!tenantId ? (
          <p className="text-sm text-muted-foreground">尚未綁定租戶</p>
        ) : prefs.isLoading ? (
          <div className="space-y-2" data-testid="config-change-notify-loading">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        ) : prefs.isError || !data ? (
          <p className="text-sm text-destructive">載入設定變更通知偏好失敗。</p>
        ) : (
          <>
            <ul className="space-y-2">
              {data.available_groups.map((group) => {
                const id = `notify-group-${group.key}`;
                return (
                  <li key={group.key} className="flex items-center gap-2">
                    <Checkbox
                      id={id}
                      checked={selected.includes(group.key)}
                      disabled={update.isPending}
                      onCheckedChange={(v) => toggle(group.key, v === true)}
                    />
                    <Label htmlFor={id}>{group.label}</Label>
                  </li>
                );
              })}
            </ul>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() => save(selected)}
                disabled={!dirty || update.isPending}
              >
                {update.isPending ? "儲存中..." : "儲存"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => save(null)}
                disabled={usingDefault || update.isPending}
              >
                還原平台預設
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
