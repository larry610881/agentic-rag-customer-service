"use client";

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
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={12} />
            <YAxis domain={[0, 100]} fontSize={12} unit="%" />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)}%`, "滿意度"]}
            />
            <Area
              type="monotone"
              dataKey="satisfaction_pct"
              stroke="hsl(var(--primary))"
              fill="hsl(var(--primary) / 0.2)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
