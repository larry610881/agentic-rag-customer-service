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
import type { BotUsageStat } from "@/types/token-usage";

interface UsageBotBarChartProps {
  data: BotUsageStat[] | undefined;
  isLoading: boolean;
}

export function UsageBotBarChart({ data, isLoading }: UsageBotBarChartProps) {
  const barData = useMemo(() => {
    if (!data?.length) return [];
    const map = new Map<string, { name: string; input: number; output: number }>();
    for (const row of data) {
      const key = row.bot_id ?? "__none__";
      const name = row.bot_name ?? "未指定";
      const prev = map.get(key);
      map.set(key, {
        name,
        input: (prev?.input ?? 0) + row.input_tokens,
        output: (prev?.output ?? 0) + row.output_tokens,
      });
    }
    return Array.from(map.values()).sort((a, b) => b.input + b.output - a.input - a.output);
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>Bot Token 比較</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!barData.length) {
    return (
      <Card>
        <CardHeader><CardTitle>Bot Token 比較</CardTitle></CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">尚無資料</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle>Bot Token 比較</CardTitle></CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
            <XAxis dataKey="name" fontSize={12} stroke="oklch(1 0 0 / 40%)" />
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
            <Bar dataKey="input" stackId="a" fill="oklch(0.65 0.20 250)" fillOpacity={0.85} name="input" radius={[0, 0, 0, 0]} />
            <Bar dataKey="output" stackId="a" fill="oklch(0.70 0.18 150)" fillOpacity={0.85} name="output" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
