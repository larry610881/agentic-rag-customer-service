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
import type { TagCount } from "@/types/feedback";

interface TopIssuesChartProps {
  data: TagCount[] | undefined;
  isLoading: boolean;
}

export function TopIssuesChart({ data, isLoading }: TopIssuesChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>常見問題標籤</CardTitle>
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
          <CardTitle>常見問題標籤</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">
            尚無問題標籤
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>常見問題標籤</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
            <XAxis type="number" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <YAxis
              type="category"
              dataKey="tag"
              width={120}
              fontSize={12}
              stroke="oklch(1 0 0 / 40%)"
            />
            <Tooltip
              formatter={(value: number) => [value, "次數"]}
              contentStyle={{ background: 'oklch(0.14 0.02 250)', border: '1px solid oklch(0.75 0.15 195 / 20%)', borderRadius: '8px' }}
            />
            <Bar
              dataKey="count"
              fill="var(--chart-hex-1)"
              fillOpacity={0.8}
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
