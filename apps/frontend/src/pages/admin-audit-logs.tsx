/** Issue #60 — 稽核紀錄頁（system_admin only）：誰在何時改了什麼設定 */

import { ClipboardList } from "lucide-react";
import { useMemo, useState } from "react";

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
import { Skeleton } from "@/components/ui/skeleton";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import {
  AuditLogsTable,
  ENTITY_TYPE_LABEL,
} from "@/features/admin/components/audit-logs-table";
import { useAuditLogs } from "@/hooks/queries/use-audit-logs";
import { useTenants } from "@/hooks/queries/use-tenants";

const PAGE_SIZE = 20;
const ENTITY_TYPES = ["guard_rules", "system_prompt", "bot", "worker", "tenant"];

export default function AdminAuditLogsPage() {
  const [tenantId, setTenantId] = useState<string | undefined>(undefined);
  const [entityType, setEntityType] = useState<string>("all");
  const [entityIdInput, setEntityIdInput] = useState("");
  const [entityId, setEntityId] = useState("");
  const [page, setPage] = useState(1);

  const filters = useMemo(
    () => ({
      tenant_id: tenantId,
      entity_type: entityType === "all" ? undefined : entityType,
      entity_id: entityId || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [tenantId, entityType, entityId, page],
  );

  const { data, isLoading, error, isFetching } = useAuditLogs(filters);
  const { data: tenantsData } = useTenants();
  const tenantNames = useMemo(
    () =>
      Object.fromEntries(
        (tenantsData?.items ?? []).map((t) => [t.id, t.name]),
      ) as Record<string, string>,
    [tenantsData],
  );

  const items = data?.items ?? [];
  const hasNext = items.length >= PAGE_SIZE;

  const applyEntityId = () => {
    setEntityId(entityIdInput.trim());
    setPage(1);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <ClipboardList className="h-6 w-6" />
        <div>
          <h1 className="text-2xl font-bold tracking-tight">稽核紀錄</h1>
          <p className="text-muted-foreground">
            安全規則、系統提示詞、機器人、Worker、租戶的設定變更歷程
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">租戶</Label>
          <AdminTenantFilter
            value={tenantId}
            onChange={(v) => {
              setTenantId(v);
              setPage(1);
            }}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-entity-type" className="text-xs text-muted-foreground">
            類型
          </Label>
          <Select
            value={entityType}
            onValueChange={(v) => {
              setEntityType(v);
              setPage(1);
            }}
          >
            <SelectTrigger id="audit-entity-type" className="w-[180px]">
              <SelectValue placeholder="全部類型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部類型</SelectItem>
              {ENTITY_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {ENTITY_TYPE_LABEL[t] ?? t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-entity-id" className="text-xs text-muted-foreground">
            對象 ID
          </Label>
          <div className="flex gap-2">
            <Input
              id="audit-entity-id"
              className="w-[260px] font-mono text-xs"
              placeholder="entity_id（完整比對）"
              value={entityIdInput}
              onChange={(e) => setEntityIdInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") applyEntityId();
              }}
            />
            <Button type="button" variant="outline" size="sm" onClick={applyEntityId}>
              套用
            </Button>
          </div>
        </div>
      </div>

      {isLoading && <Skeleton className="h-64 w-full" />}
      {error && (
        <p className="text-sm text-destructive">
          載入稽核紀錄失敗：{(error as Error).message}
        </p>
      )}
      {!isLoading && !error && (
        <AuditLogsTable items={items} tenantNames={tenantNames} />
      )}

      <div className="flex items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={page <= 1 || isFetching}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          上一頁
        </Button>
        <span className="text-sm text-muted-foreground">第 {page} 頁</span>
        <Button
          variant="outline"
          size="sm"
          disabled={!hasNext || isFetching}
          onClick={() => setPage((p) => p + 1)}
        >
          下一頁
        </Button>
      </div>
    </div>
  );
}
