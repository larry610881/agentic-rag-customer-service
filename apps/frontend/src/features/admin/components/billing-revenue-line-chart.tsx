import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/format-currency";
import type { MonthlyRevenuePoint } from "@/hooks/queries/use-billing-dashboard";

interface BillingRevenueLineChartProps {
  data: MonthlyRevenuePoint[] | undefined;
  isLoading: boolean;
}

export function BillingRevenueLineChart({
  data,
  isLoading,
}: BillingRevenueLineChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>月營收趨勢</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[300px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>月營收趨勢</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">
            該範圍尚無營收資料
          </p>
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((d) => ({
    cycle: d.cycle_year_month,
    amount: Number(d.total_amount),
    transactions: d.transaction_count,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>月營收趨勢</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
            <XAxis dataKey="cycle" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <YAxis fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const entry = payload[0].payload as {
                  cycle: string;
                  amount: number;
                  transactions: number;
                };
                return (
                  <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
                    <p className="font-medium">{entry.cycle}</p>
                    <p className="text-muted-foreground">
                      營收：
                      <span className="text-foreground font-mono">
                        {formatCurrency(entry.amount)}
                      </span>
                    </p>
                    <p className="text-muted-foreground">
                      交易數：
                      <span className="text-foreground font-mono">
                        {entry.transactions}
                      </span>
                    </p>
                  </div>
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="amount"
              stroke="var(--chart-hex-1)"
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
