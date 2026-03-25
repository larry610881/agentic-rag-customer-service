import { useMemo } from "react";
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
import type { TenantBotUsageStat } from "@/types/token-usage";

interface TokenUsageBarChartProps {
  data: TenantBotUsageStat[] | undefined;
  isLoading: boolean;
}

export function TokenUsageBarChart({ data, isLoading }: TokenUsageBarChartProps) {
  const chartData = useMemo(() => {
    if (!data?.length) return [];
    const byBot = new Map<string, { input: number; output: number }>();
    for (const row of data) {
      const key = row.bot_name ?? "(未指定 Bot)";
      const prev = byBot.get(key) ?? { input: 0, output: 0 };
      byBot.set(key, {
        input: prev.input + row.input_tokens,
        output: prev.output + row.output_tokens,
      });
    }
    return Array.from(byBot.entries())
      .map(([bot, tokens]) => ({
        bot,
        input_tokens: tokens.input,
        output_tokens: tokens.output,
      }))
      .sort((a, b) => b.input_tokens + b.output_tokens - (a.input_tokens + a.output_tokens));
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>Token 用量（按 Bot）</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!chartData.length) {
    return (
      <Card>
        <CardHeader><CardTitle>Token 用量（按 Bot）</CardTitle></CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">尚無用量資料</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle>Token 用量（按 Bot）</CardTitle></CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} barSize={12}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
            <XAxis dataKey="bot" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <YAxis fontSize={12} stroke="oklch(1 0 0 / 40%)" />
            <Tooltip
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any, name: any) => [
                Number(value).toLocaleString(),
                name === "input_tokens" ? "輸入 Tokens" : "輸出 Tokens",
              ]}
              contentStyle={{
                background: "oklch(0.14 0.02 250)",
                border: "1px solid oklch(0.75 0.15 195 / 20%)",
                borderRadius: "8px",
              }}
            />
            <Bar
              dataKey="input_tokens"
              stackId="tokens"
              fill="var(--chart-hex-1)"
              name="input_tokens"
            />
            <Bar
              dataKey="output_tokens"
              stackId="tokens"
              fill="var(--chart-hex-2)"
              name="output_tokens"
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
