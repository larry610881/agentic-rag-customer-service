import { Lock } from "lucide-react";

import {
  GUARD_LOCKED_HINT,
  guardSourceLabel,
  guardStageDefsFor,
} from "@/features/guard-stages/guard-stage-labels";
import { useTenantGuardSettings } from "@/hooks/queries/use-guard-stages";
import { useAuthStore } from "@/stores/use-auth-store";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * Issue #75 — 租戶端唯讀頁（tenant_admin / system_admin）：本租戶目前生效的防護階段與來源。
 * 讀 GET /admin/guard/settings/tenants/{own}（tenant_admin 只能讀自己）。
 * 各 bot 可在機器人設定「防護階段」區塊加嚴；鎖定時由系統管理員設定、此處與 bot 皆唯讀。
 */
export default function GuardStatusPage() {
  const tenantId = useAuthStore((s) => s.tenantId);
  const settings = useTenantGuardSettings(tenantId);
  const effective = settings.data?.effective;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">防護階段</h1>
        <p className="text-muted-foreground">
          本租戶對話管線目前生效的防護階段。底線與系統預設不可關閉；各機器人可於設定中另行加嚴。
        </p>
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold">生效階段</h2>
          {effective && <Badge variant="secondary">方案：{effective.profile}</Badge>}
          {effective?.locked && (
            <Badge variant="destructive" className="gap-1">
              <Lock className="h-3 w-3" />
              已鎖定：{GUARD_LOCKED_HINT}
            </Badge>
          )}
        </div>
        {!tenantId ? (
          <p className="text-muted-foreground">無法辨識目前租戶</p>
        ) : settings.isLoading ? (
          <p className="text-muted-foreground">載入中…</p>
        ) : settings.isError || !effective ? (
          <p className="text-destructive">無法載入設定</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-1/2">階段</TableHead>
                  <TableHead className="w-24">狀態</TableHead>
                  <TableHead className="w-32">來源</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {guardStageDefsFor().map((def) => {
                  const enabled = effective.stages.includes(def.key);
                  const isRequired = effective.required.includes(def.key);
                  const source = effective.source_map[def.key];
                  return (
                    <TableRow key={def.key}>
                      <TableCell>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{def.label}</span>
                          {def.comingSoon && <Badge variant="outline">即將推出</Badge>}
                        </div>
                        <p className="text-xs text-muted-foreground">{def.description}</p>
                      </TableCell>
                      <TableCell data-testid={`guard-status-${def.key}`}>
                        {enabled ? (
                          <Badge variant="default">啟用</Badge>
                        ) : (
                          <Badge variant="outline">未啟用</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {enabled ? (
                          <Badge variant={isRequired ? "default" : "secondary"} className="font-normal">
                            {isRequired ? "底線" : guardSourceLabel(source)}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  );
}
