"use client";

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
import type { ModelCostStat } from "@/types/feedback";

interface TokenCostTableProps {
  data: ModelCostStat[] | undefined;
  isLoading: boolean;
}

export function TokenCostTable({ data, isLoading }: TokenCostTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Token 成本統計</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[200px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Token 成本統計</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-8 text-center text-muted-foreground">
            尚無成本資料
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Token 成本統計</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>模型</TableHead>
              <TableHead className="text-right">訊息數</TableHead>
              <TableHead className="text-right">輸入 Tokens</TableHead>
              <TableHead className="text-right">輸出 Tokens</TableHead>
              <TableHead className="text-right">平均延遲</TableHead>
              <TableHead className="text-right">預估成本</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow key={row.model}>
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
                  {row.avg_latency_ms.toFixed(0)} ms
                </TableCell>
                <TableCell className="text-right">
                  ${row.estimated_cost.toFixed(4)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
