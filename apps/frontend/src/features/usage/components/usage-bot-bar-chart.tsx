import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { MonthlyUsageStat } from "@/types/token-usage";

interface UsageMonthlyBarChartProps {
  data: MonthlyUsageStat[] | undefined;
  isLoading: boolean;
}

export function UsageMonthlyBarChart({ data, isLoading }: UsageMonthlyBarChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>每月用量比較</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!data?.length) {
    return (
      <Card>
        <CardHeader><CardTitle>每月用量比較</CardTitle></CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">尚無資料</p>
        </CardContent>
      </Card>
    );
  }

  const barData = data.map((d) => ({
    label: d.month.slice(5) + "月", // "01月" from "2026-01"
    input: d.input_tokens,
    output: d.output_tokens,
  }));

  return (
    <Card>
      <CardHeader><CardTitle>每月用量比較</CardTitle></CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
            <XAxis dataKey="label" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <YAxis fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <Tooltip
              contentStyle={{
                background: "oklch(0.14 0.02 250)",
                border: "1px solid oklch(0.75 0.15 195 / 20%)",
                borderRadius: "8px",
              }}
              formatter={(value: number, name: string) => [
                value.toLocaleString(),
                name === "input" ? "輸入 Tokens" : "輸出 Tokens",
              ]}
            />
            <Bar dataKey="input" stackId="a" fill="oklch(0.65 0.20 250)" fillOpacity={0.85} name="input" />
            <Bar dataKey="output" stackId="a" fill="oklch(0.70 0.18 150)" fillOpacity={0.85} name="output" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
