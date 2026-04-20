import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency } from "@/lib/format-currency";
import type { TopTenantItem } from "@/hooks/queries/use-billing-dashboard";

interface BillingTopTenantsTableProps {
  data: TopTenantItem[] | undefined;
  isLoading: boolean;
}

export function BillingTopTenantsTable({
  data,
  isLoading,
}: BillingTopTenantsTableProps) {
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Top 租戶（按累計營收）</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Top 租戶（按累計營收）</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">
            該範圍尚無交易
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top 租戶（按累計營收）</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead>租戶</TableHead>
              <TableHead className="text-right">交易數</TableHead>
              <TableHead className="text-right">累計營收</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((t, idx) => (
              <TableRow
                key={t.tenant_id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() =>
                  navigate(`/admin/quota-events?tenant_id=${t.tenant_id}`)
                }
              >
                <TableCell className="font-mono text-muted-foreground">
                  {idx + 1}
                </TableCell>
                <TableCell className="font-medium">{t.tenant_name || "—"}</TableCell>
                <TableCell className="text-right font-mono">
                  {t.transaction_count}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {formatCurrency(t.total_amount)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
