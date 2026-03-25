import { useState } from "react";
import {
  Bar,
  BarChart,
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
import type { MonthlyUsageStat } from "@/types/token-usage";

interface TrendDataPoint {
  label: string;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
}

type ChartType = "line" | "bar";

interface UsageTrendChartProps {
  data: TrendDataPoint[] | undefined;
  monthlyData?: MonthlyUsageStat[] | undefined;
  isLoading: boolean;
  mode: "month" | "year";
}

const tooltipStyle = {
  background: "oklch(0.14 0.02 250)",
  border: "1px solid oklch(0.75 0.15 195 / 20%)",
  borderRadius: "8px",
};

function formatLabel(value: number, name: string) {
  return [
    value.toLocaleString(),
    name === "total_tokens" || name === "total"
      ? "總量"
      : name === "input_tokens" || name === "input"
        ? "輸入"
        : "輸出",
  ] as [string, string];
}

export function UsageTrendLineChart({
  data,
  monthlyData,
  isLoading,
  mode,
}: UsageTrendChartProps) {
  const [chartType, setChartType] = useState<ChartType>("line");
  const title = mode === "month" ? "每日用量趨勢" : "每月用量趨勢";

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!data?.length) {
    return (
      <Card>
        <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">尚無趨勢資料</p>
        </CardContent>
      </Card>
    );
  }

  // Bar chart data: for month mode use daily total, for year mode use monthly input/output
  const barData =
    mode === "year" && monthlyData?.length
      ? monthlyData.map((d) => ({
          label: d.month.slice(5) + "月",
          input: d.input_tokens,
          output: d.output_tokens,
        }))
      : data.map((d) => ({
          label: d.label,
          total: d.total_tokens,
        }));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>{title}</CardTitle>
        <div className="flex gap-1 rounded-md border p-0.5">
          <button
            className={`rounded px-3 py-1 text-xs transition-colors ${
              chartType === "line"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setChartType("line")}
          >
            折線圖
          </button>
          <button
            className={`rounded px-3 py-1 text-xs transition-colors ${
              chartType === "bar"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setChartType("bar")}
          >
            長條圖
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          {chartType === "line" ? (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
              <XAxis dataKey="label" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
              <YAxis fontSize={12} stroke="oklch(1 0 0 / 40%)" />
              <Tooltip contentStyle={tooltipStyle} formatter={formatLabel} />
              {mode === "month" ? (
                <Line
                  type="monotone"
                  dataKey="total_tokens"
                  stroke="oklch(0.65 0.20 250)"
                  strokeWidth={2}
                  dot={false}
                  name="total_tokens"
                />
              ) : (
                <>
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
                </>
              )}
            </LineChart>
          ) : (
            <BarChart data={barData} barSize={12}>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
              <XAxis dataKey="label" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
              <YAxis fontSize={12} stroke="oklch(1 0 0 / 40%)" />
              <Tooltip contentStyle={tooltipStyle} formatter={formatLabel} />
              {mode === "month" ? (
                <Bar
                  dataKey="total"
                  fill="oklch(0.65 0.20 250)"
                  fillOpacity={0.85}
                  name="total"
                  radius={[2, 2, 0, 0]}
                />
              ) : (
                <>
                  <Bar
                    dataKey="input"
                    stackId="a"
                    fill="oklch(0.65 0.20 250)"
                    fillOpacity={0.85}
                    name="input"
                  />
                  <Bar
                    dataKey="output"
                    stackId="a"
                    fill="oklch(0.70 0.18 150)"
                    fillOpacity={0.85}
                    name="output"
                    radius={[2, 2, 0, 0]}
                  />
                </>
              )}
            </BarChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
