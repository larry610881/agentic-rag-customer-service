import { RefreshCw } from "lucide-react";

import { AbuseControlsTable } from "@/features/abuse-control/components/abuse-controls-table";
import { AbuseEffectiveTable } from "@/features/abuse-control/components/abuse-effective-table";
import { profileLabel } from "@/features/abuse-control/abuse-setting-labels";
import {
  useAbuseControls,
  useTenantAbuseSettings,
} from "@/hooks/queries/use-abuse-control";
import { useAuthStore } from "@/stores/use-auth-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * 租戶端唯讀頁（tenant_admin / system_admin）：顯示自己租戶的生效設定與受控主體。
 * 設定由系統管理員在 /admin/abuse-control 維護；受控主體只給遮罩值、不可解除。
 */
export default function AbuseStatusPage() {
  const tenantId = useAuthStore((s) => s.tenantId);
  const settings = useTenantAbuseSettings(tenantId);
  const controls = useAbuseControls(tenantId ?? undefined);

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">異常控管狀態</h1>
        <p className="text-muted-foreground">
          本租戶的異常行為控管生效設定與目前受控的主體。設定由系統管理員設定，此頁僅供檢視。
        </p>
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold">生效設定</h2>
          {settings.data && (
            <Badge variant="secondary">方案：{profileLabel(settings.data.profile)}</Badge>
          )}
          <Badge variant="outline">由系統管理員設定</Badge>
        </div>
        {!tenantId ? (
          <p className="text-muted-foreground">無法辨識目前租戶</p>
        ) : settings.isLoading ? (
          <p className="text-muted-foreground">載入中…</p>
        ) : settings.isError || !settings.data ? (
          <p className="text-destructive">無法載入設定</p>
        ) : (
          <AbuseEffectiveTable
            values={settings.data.effective}
            layers={[{ label: "租戶覆寫", overrides: settings.data.overrides }]}
            fallbackSource="方案／平台預設"
          />
        )}
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">受控中的主體</h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => controls.refetch()}
            disabled={controls.isFetching}
          >
            <RefreshCw className={`mr-1 h-4 w-4 ${controls.isFetching ? "animate-spin" : ""}`} />
            重新整理
          </Button>
          <span className="text-xs text-muted-foreground">每 30 秒自動更新；主體識別已遮罩</span>
        </div>
        {controls.isError ? (
          <p className="text-destructive">無法載入受控清單</p>
        ) : (
          <AbuseControlsTable
            items={controls.data}
            isLoading={controls.isLoading}
            fetchedAt={controls.dataUpdatedAt || undefined}
          />
        )}
      </section>
    </div>
  );
}
