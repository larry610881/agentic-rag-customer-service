import { useMemo } from "react";
import type { PieLabelRenderProps } from "recharts";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { TenantBotUsageStat } from "@/types/token-usage";

const COLORS = [
  "var(--chart-hex-1)",
  "var(--chart-hex-2)",
  "var(--chart-hex-3)",
  "var(--chart-hex-4)",
  "var(--chart-hex-5)",
];

interface TokenUsagePieChartProps {
  data: TenantBotUsageStat[] | undefined;
  isLoading: boolean;
}

export function TokenUsagePieChart({ data, isLoading }: TokenUsagePieChartProps) {
  const chartData = useMemo(() => {
    if (!data?.length) return [];
    const byModel = new Map<string, number>();
    for (const row of data) {
      byModel.set(row.model, (byModel.get(row.model) ?? 0) + row.estimated_cost);
    }
    return Array.from(byModel.entries())
      .map(([model, cost]) => ({ model, cost: Number(cost.toFixed(4)) }))
      .sort((a, b) => b.cost - a.cost);
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>成本分布（按模型）</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!chartData.length) {
    return (
      <Card>
        <CardHeader><CardTitle>成本分布（按模型）</CardTitle></CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">尚無用量資料</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle>成本分布（按模型）</CardTitle></CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="cost"
              nameKey="model"
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
                const model = entry.name ?? "";
                const cost = Number(entry.value ?? 0);
                const total = chartData.reduce((s, d) => s + d.cost, 0);
                const pct = total > 0 ? ((cost / total) * 100).toFixed(1) : "0.0";
                return (
                  <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
                    <p className="font-medium">{model}</p>
                    <p className="text-muted-foreground">
                      預估成本：<span className="text-foreground font-mono">${cost.toFixed(4)}</span>
                    </p>
                    <p className="text-muted-foreground">
                      佔比：<span className="text-foreground font-mono">{pct}%</span>
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
