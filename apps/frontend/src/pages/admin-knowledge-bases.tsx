import { useState } from "react";
import { Link } from "react-router-dom";
import { useAdminKnowledgeBases } from "@/hooks/queries/use-admin";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export default function AdminKnowledgeBasesPage() {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const { data: knowledgeBases, isLoading, isError } = useAdminKnowledgeBases(tenantId);
  const tenantNameMap = useTenantNameMap();

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">所有知識庫（跨租戶總覽）</h2>
        <div className="flex items-center gap-3">
          <AdminTenantFilter value={tenantId} onChange={setTenantId} />
          <Badge variant="outline">唯讀</Badge>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded" />
          ))}
        </div>
      )}

      {isError && (
        <p className="text-destructive">載入知識庫失敗。</p>
      )}

      {knowledgeBases && knowledgeBases.length === 0 && (
        <p className="text-muted-foreground">目前沒有任何知識庫。</p>
      )}

      {knowledgeBases && knowledgeBases.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>說明</TableHead>
                <TableHead>租戶</TableHead>
                <TableHead>建立時間</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {knowledgeBases.map((kb) => (
                <TableRow key={kb.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/admin/knowledge-bases/${kb.id}`}
                      className="hover:underline underline-offset-4"
                    >
                      {kb.name}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-muted-foreground">
                    {kb.description || "-"}
                  </TableCell>
                  <TableCell>
                    {tenantNameMap.get(kb.tenant_id) ?? kb.tenant_id.slice(0, 8)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(kb.created_at).toLocaleDateString("zh-TW")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
