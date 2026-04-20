import type { PieLabelRenderProps } from "recharts";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/format-currency";
import type { PlanRevenuePoint } from "@/hooks/queries/use-billing-dashboard";

const COLORS = [
  "var(--chart-hex-1)",
  "var(--chart-hex-2)",
  "var(--chart-hex-3)",
  "var(--chart-hex-4)",
  "var(--chart-hex-5)",
];

interface BillingByPlanPieChartProps {
  data: PlanRevenuePoint[] | undefined;
  isLoading: boolean;
}

export function BillingByPlanPieChart({
  data,
  isLoading,
}: BillingByPlanPieChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>方案營收分布</CardTitle>
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
          <CardTitle>方案營收分布</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">
            該範圍尚無方案資料
          </p>
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((d) => ({
    plan: d.plan_name,
    amount: Number(d.total_amount),
    count: d.transaction_count,
  }));

  const total = chartData.reduce((s, d) => s + d.amount, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>方案營收分布</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="amount"
              nameKey="plan"
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={(props: PieLabelRenderProps) =>
                `${props.name} (${(((props.percent ?? 0) as number) * 100).toFixed(1)}%)`
              }
              labelLine={false}
            >
              {chartData.map((_, idx) => (
                <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const entry = payload[0];
                const plan = entry.name ?? "";
                const amount = Number(entry.value ?? 0);
                const pct = total > 0 ? ((amount / total) * 100).toFixed(1) : "0.0";
                return (
                  <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
                    <p className="font-medium">{plan}</p>
                    <p className="text-muted-foreground">
                      營收：
                      <span className="text-foreground font-mono">
                        {formatCurrency(amount)}
                      </span>
                    </p>
                    <p className="text-muted-foreground">
                      佔比：
                      <span className="text-foreground font-mono">{pct}%</span>
                    </p>
                  </div>
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
