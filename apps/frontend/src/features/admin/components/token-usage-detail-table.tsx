import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import type { TenantBotUsageStat } from "@/types/token-usage";
import { getRequestTypeLabel, inferUsageSource } from "@/types/token-usage";

interface TokenUsageDetailTableProps {
  data: TenantBotUsageStat[] | undefined;
  isLoading: boolean;
}

export function TokenUsageDetailTable({ data, isLoading }: TokenUsageDetailTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>用量明細</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[200px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!data?.length) {
    return (
      <Card>
        <CardHeader><CardTitle>用量明細</CardTitle></CardHeader>
        <CardContent>
          <p className="py-8 text-center text-muted-foreground">尚無用量資料</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle>用量明細</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>租戶</TableHead>
              <TableHead>類型</TableHead>
              <TableHead>來源</TableHead>
              <TableHead>模型</TableHead>
              <TableHead className="text-right">次數</TableHead>
              <TableHead className="text-right">輸入 Tokens</TableHead>
              <TableHead className="text-right">輸出 Tokens</TableHead>
              <TableHead className="text-right">快取讀取</TableHead>
              <TableHead className="text-right">快取寫入</TableHead>
              <TableHead className="text-right">預估成本</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row, idx) => {
              const src = inferUsageSource(row);
              return (
              <TableRow key={`${row.tenant_id}-${row.bot_id ?? row.kb_id ?? "sys"}-${row.model}-${row.request_type}-${idx}`}>
                <TableCell>{row.tenant_name}</TableCell>
                <TableCell>{getRequestTypeLabel(row.request_type)}</TableCell>
                <TableCell>
                  {src.href ? (
                    <Link
                      to={src.href}
                      className="inline-flex items-center gap-1 hover:underline underline-offset-4"
                    >
                      <span>{src.icon}</span>
                      <span>{src.name}</span>
                    </Link>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-muted-foreground">
                      <span>{src.icon}</span>
                      <span>{src.name}</span>
                    </span>
                  )}
                </TableCell>
                <TableCell className="font-medium">{row.model}</TableCell>
                <TableCell className="text-right">
                  {row.message_count.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {row.input_tokens.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {row.output_tokens.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {row.cache_read_tokens.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {row.cache_creation_tokens.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  ${row.estimated_cost.toFixed(4)}
                </TableCell>
              </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
