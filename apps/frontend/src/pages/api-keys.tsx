/** Issue #67 P2 — 租戶 API 金鑰管理頁 */
import { useState } from "react";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiKeyTable } from "@/features/api-keys/components/api-key-table";
import { CreateApiKeyDialog } from "@/features/api-keys/components/create-api-key-dialog";
import { useTenants } from "@/hooks/queries/use-tenants";
import { useAuthStore } from "@/stores/use-auth-store";

const ALL_TENANTS = "__all__";

export default function ApiKeysPage() {
  const role = useAuthStore((s) => s.role);
  const isSystemAdmin = role === "system_admin";
  const [tenantFilter, setTenantFilter] = useState<string>(ALL_TENANTS);
  const selectedTenantId = tenantFilter === ALL_TENANTS ? undefined : tenantFilter;

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">API 金鑰</h2>
          <p className="text-sm text-muted-foreground">
            供外部系統以 client_credentials 方式呼叫聊天 API；撤銷後立即失效。
          </p>
        </div>
        <CreateApiKeyDialog
          tenantId={isSystemAdmin ? selectedTenantId : undefined}
          disabled={isSystemAdmin && !selectedTenantId}
        />
      </div>

      {isSystemAdmin && (
        <SystemAdminTenantFilter value={tenantFilter} onChange={setTenantFilter} />
      )}

      <ApiKeyTable tenantId={isSystemAdmin ? selectedTenantId : undefined} />
    </div>
  );
}

function SystemAdminTenantFilter({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const { data } = useTenants(1, 100);
  return (
    <div className="flex items-center gap-3">
      <Label htmlFor="api-keys-tenant-filter">租戶</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id="api-keys-tenant-filter" className="w-64">
          <SelectValue placeholder="選擇租戶" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_TENANTS}>全部租戶（僅檢視）</SelectItem>
          {data?.items.map((t) => (
            <SelectItem key={t.id} value={t.id}>
              {t.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {value === ALL_TENANTS && (
        <span className="text-xs text-muted-foreground">建立金鑰前請先選擇租戶</span>
      )}
    </div>
  );
}
