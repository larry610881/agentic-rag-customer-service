import { useMemo } from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { BotUsageStat } from "@/types/token-usage";

const COLORS = [
  "oklch(0.65 0.20 250)",
  "oklch(0.70 0.18 150)",
  "oklch(0.65 0.20 25)",
  "oklch(0.70 0.16 80)",
  "oklch(0.60 0.15 300)",
  "oklch(0.55 0.12 330)",
  "oklch(0.65 0.18 50)",
];

interface UsageBotPieChartProps {
  data: BotUsageStat[] | undefined;
  isLoading: boolean;
}

export function UsageBotPieChart({ data, isLoading }: UsageBotPieChartProps) {
  const botData = useMemo(() => {
    if (!data?.length) return [];
    const map = new Map<string, { name: string; tokens: number }>();
    for (const row of data) {
      const key = row.bot_id ?? "__none__";
      const name = row.bot_name ?? "未指定";
      const prev = map.get(key);
      map.set(key, {
        name,
        tokens: (prev?.tokens ?? 0) + row.total_tokens,
      });
    }
    return Array.from(map.values()).sort((a, b) => b.tokens - a.tokens);
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>Bot Token 佔比</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  if (!botData.length) {
    return (
      <Card>
        <CardHeader><CardTitle>Bot Token 佔比</CardTitle></CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">尚無資料</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle>Bot Token 佔比</CardTitle></CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={botData}
              dataKey="tokens"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={({ name, percent }) =>
                `${name} ${(percent * 100).toFixed(0)}%`
              }
              labelLine={false}
            >
              {botData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} fillOpacity={0.85} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "oklch(0.14 0.02 250)",
                border: "1px solid oklch(0.75 0.15 195 / 20%)",
                borderRadius: "8px",
              }}
              formatter={(value: number) => [value.toLocaleString(), "Tokens"]}
            />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
