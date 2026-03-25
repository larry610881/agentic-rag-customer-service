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
import type { DailyUsageStat } from "@/types/token-usage";

interface UsageDailyLineChartProps {
  data: DailyUsageStat[] | undefined;
  isLoading: boolean;
}

export function UsageDailyLineChart({ data, isLoading }: UsageDailyLineChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>每日用量趨勢</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!data?.length) {
    return (
      <Card>
        <CardHeader><CardTitle>每日用量趨勢</CardTitle></CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">尚無趨勢資料</p>
        </CardContent>
      </Card>
    );
  }

  // Format dates for display (MM/DD)
  const chartData = data.map((d) => ({
    ...d,
    label: d.date.slice(5), // "03-25" from "2026-03-25"
  }));

  return (
    <Card>
      <CardHeader><CardTitle>每日用量趨勢</CardTitle></CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
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
                name === "input_tokens" ? "輸入" : name === "output_tokens" ? "輸出" : "總量",
              ]}
            />
            <Line
              type="monotone"
              dataKey="input_tokens"
              stroke="oklch(0.65 0.20 250)"
              strokeWidth={2}
              dot={false}
              name="input_tokens"
            />
            <Line
              type="monotone"
              dataKey="output_tokens"
              stroke="oklch(0.70 0.18 150)"
              strokeWidth={2}
              dot={false}
              name="output_tokens"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
