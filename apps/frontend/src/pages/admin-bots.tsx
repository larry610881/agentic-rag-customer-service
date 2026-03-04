import { useAdminBots } from "@/hooks/queries/use-admin";
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
  const { data: bots, isLoading, isError } = useAdminBots();

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">所有機器人（跨租戶總覽）</h2>
        <Badge variant="outline">唯讀</Badge>
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

      {bots && bots.length === 0 && (
        <p className="text-muted-foreground">目前沒有任何機器人。</p>
      )}

      {bots && bots.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>說明</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead>租戶 ID</TableHead>
                <TableHead>LLM</TableHead>
                <TableHead>建立時間</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {bots.map((bot) => (
                <TableRow key={bot.id}>
                  <TableCell className="font-medium">{bot.name}</TableCell>
                  <TableCell className="max-w-xs truncate text-muted-foreground">
                    {bot.description || "-"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={bot.is_active ? "default" : "secondary"}>
                      {bot.is_active ? "啟用" : "停用"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs">{bot.tenant_id.slice(0, 8)}...</code>
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
    </div>
  );
}
