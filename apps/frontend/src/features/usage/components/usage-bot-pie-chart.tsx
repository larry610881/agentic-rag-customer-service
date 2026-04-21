import { useMemo, useState } from "react";
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
import { getRequestTypeLabel } from "@/types/token-usage";
import { CHART_COLORS, CHART_LABEL_FILL, CHART_TOOLTIP } from "@/lib/chart-styles";

type ViewMode = "type" | "bot" | "model";

interface UsagePieChartProps {
  data: BotUsageStat[] | undefined;
  isLoading: boolean;
}

function aggregate(
  data: BotUsageStat[],
  viewMode: ViewMode,
): { name: string; tokens: number }[] {
  const map = new Map<string, { name: string; tokens: number }>();
  for (const row of data) {
    let key: string;
    let name: string;
    if (viewMode === "type") {
      key = row.request_type;
      name = getRequestTypeLabel(row.request_type);
    } else if (viewMode === "bot") {
      key = row.bot_id ?? "__none__";
      name = row.bot_name ?? "系統（無 Bot）";
    } else {
      key = row.model;
      name = row.model;
    }
    const prev = map.get(key);
    map.set(key, {
      name,
      tokens: (prev?.tokens ?? 0) + row.total_tokens,
    });
  }
  return Array.from(map.values()).sort((a, b) => b.tokens - a.tokens);
}

const VIEW_OPTIONS: { value: ViewMode; label: string }[] = [
  { value: "type", label: "按類型" },
  { value: "bot", label: "按 Bot" },
  { value: "model", label: "按 Model" },
];

export function UsagePieChart({ data, isLoading }: UsagePieChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("type");

  const chartData = useMemo(
    () => (data?.length ? aggregate(data, viewMode) : []),
    [data, viewMode],
  );

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>Token 佔比</CardTitle></CardHeader>
        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Token 佔比</CardTitle>
        <div className="flex gap-1 rounded-md border p-0.5">
          {VIEW_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`rounded px-3 py-1 text-xs transition-colors ${
                viewMode === opt.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setViewMode(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {!chartData.length ? (
          <p className="py-12 text-center text-muted-foreground">尚無資料</p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="tokens"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ name, percent }) =>
                  `${name} ${(percent * 100).toFixed(0)}%`
                }
                labelLine={false}
                stroke={CHART_LABEL_FILL}
                strokeWidth={0.5}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.85} />
                ))}
              </Pie>
              <Tooltip
                {...CHART_TOOLTIP}
                formatter={(value: number) => [value.toLocaleString(), "Tokens"]}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
