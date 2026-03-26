import { useState } from "react";
import { useTenants } from "@/hooks/queries/use-tenants";
import { TenantConfigDialog } from "@/features/admin/components/tenant-config-dialog";
import { CreateTenantDialog } from "@/features/admin/components/create-tenant-dialog";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { usePagination } from "@/hooks/use-pagination";
import type { Tenant } from "@/types/auth";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Settings } from "lucide-react";

const SYSTEM_TENANT_ID = "00000000-0000-0000-0000-000000000000";

export default function AdminTenantsPage() {
  const { page, setPage } = usePagination();
  const { data, isLoading } = useTenants(page);
  const [configTenant, setConfigTenant] = useState<Tenant | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  // Exclude system tenant from display
  const realTenants = data?.items?.filter((t) => t.id !== SYSTEM_TENANT_ID) ?? [];

  const handleConfig = (tenant: Tenant) => {
    setConfigTenant(tenant);
    setDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">租戶管理</h1>
          <p className="text-muted-foreground">管理租戶設定與資源上限</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          新增租戶
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">載入中...</p>
      ) : realTenants.length === 0 ? (
        <p className="text-muted-foreground">尚無租戶</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>方案</TableHead>
                <TableHead>月 Token 上限</TableHead>
                <TableHead>建立時間</TableHead>
                <TableHead className="w-[80px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {realTenants.map((tenant) => (
                <TableRow key={tenant.id}>
                  <TableCell className="font-medium">{tenant.name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{tenant.plan}</Badge>
                  </TableCell>
                  <TableCell>
                    {tenant.monthly_token_limit != null
                      ? tenant.monthly_token_limit.toLocaleString()
                      : "不限制"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {new Date(tenant.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleConfig(tenant)}
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {data && (
        <PaginationControls
          page={page}
          totalPages={data.total_pages}
          onPageChange={setPage}
        />
      )}

      <TenantConfigDialog
        tenant={configTenant}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />

      <CreateTenantDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
