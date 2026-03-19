import { useState } from "react";
import { Link } from "react-router-dom";
import { useAdminBots } from "@/hooks/queries/use-admin";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { usePagination } from "@/hooks/use-pagination";
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

export default function AdminBotsPage() {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const { page, setPage } = usePagination();
  const { data, isLoading, isError } = useAdminBots(tenantId, page);
  const tenantNameMap = useTenantNameMap();

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">所有機器人（跨租戶總覽）</h2>
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
        <p className="text-destructive">載入機器人失敗。</p>
      )}

      {data && data.items.length === 0 && (
        <p className="text-muted-foreground">目前沒有任何機器人。</p>
      )}

      {data && data.items.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>說明</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead>租戶</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>LLM</TableHead>
                <TableHead>建立時間</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((bot) => (
                <TableRow key={bot.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/admin/bots/${bot.id}`}
                      className="hover:underline underline-offset-4"
                    >
                      {bot.name}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-muted-foreground">
                    {bot.description || "-"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={bot.is_active ? "default" : "secondary"}>
                      {bot.is_active ? "啟用" : "停用"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {tenantNameMap.get(bot.tenant_id) ?? bot.tenant_id.slice(0, 8)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={bot.agent_mode === "react" ? "default" : "outline"}>
                      {bot.agent_mode === "react" ? "ReAct" : "Router"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {bot.llm_model || bot.llm_provider || "-"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(bot.created_at).toLocaleDateString("zh-TW")}
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
    </div>
  );
}
