import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DailyFeedbackStat } from "@/types/feedback";

interface SatisfactionTrendChartProps {
  data: DailyFeedbackStat[] | undefined;
  isLoading: boolean;
}

export function SatisfactionTrendChart({
  data,
  isLoading,
}: SatisfactionTrendChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>滿意度趨勢</CardTitle>
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
          <CardTitle>滿意度趨勢</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">
            尚無趨勢資料
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>滿意度趨勢</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
            <XAxis dataKey="date" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <YAxis domain={[0, 100]} fontSize={12} unit="%" stroke="oklch(1 0 0 / 40%)" />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)}%`, "滿意度"]}
              contentStyle={{ background: 'oklch(0.14 0.02 250)', border: '1px solid oklch(0.75 0.15 195 / 20%)', borderRadius: '8px' }}
            />
            <Area
              type="monotone"
              dataKey="satisfaction_pct"
              stroke="var(--chart-hex-1)"
              fill="var(--chart-hex-1)"
              fillOpacity={0.15}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
