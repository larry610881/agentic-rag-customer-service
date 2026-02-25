"use client";

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
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" fontSize={12} />
            <YAxis
              type="category"
              dataKey="tag"
              width={120}
              fontSize={12}
            />
            <Tooltip formatter={(value: number) => [value, "次數"]} />
            <Bar
              dataKey="count"
              fill="hsl(var(--primary))"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
