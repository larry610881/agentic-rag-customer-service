import { useAuthStore } from "@/stores/use-auth-store";
import { ConfigChangeNotifyCard } from "@/features/settings/components/config-change-notify-card";

/**
 * Issue #77 — 租戶設定頁（tenant_admin / system_admin）。
 * 目前只有「設定變更通知」；日後租戶層級的偏好設定集中放這裡。
 */
export default function TenantSettingsPage() {
  const tenantId = useAuthStore((s) => s.tenantId);

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">租戶設定</h1>
        <p className="text-muted-foreground">本租戶的通知偏好。</p>
      </div>
      <ConfigChangeNotifyCard tenantId={tenantId} />
    </div>
  );
}
