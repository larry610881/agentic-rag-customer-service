import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { TagCount } from "@/types/feedback";

const TAG_LABELS: Record<string, string> = {
  irrelevant: "不相關",
  incorrect: "不正確",
  incomplete: "不完整",
  offensive: "語氣不好",
  slow: "回應太慢",
  hallucination: "幻覺",
  other: "其他",
  "答案不正確": "答案不正確",
  "不完整": "不完整",
  "沒回答問題": "沒回答問題",
  "語氣不好": "語氣不好",
};

const BAR_COLORS = [
  "oklch(0.65 0.20 25)",   // 紅橘
  "oklch(0.65 0.18 50)",   // 橘
  "oklch(0.70 0.16 80)",   // 黃
  "oklch(0.65 0.15 150)",  // 綠
  "oklch(0.60 0.18 250)",  // 藍
  "oklch(0.60 0.15 300)",  // 紫
  "oklch(0.55 0.12 330)",  // 桃紅
];

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

  // Map tags to Chinese labels
  const localizedData = data.map((d) => ({
    ...d,
    label: TAG_LABELS[d.tag] ?? d.tag,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>常見問題標籤</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={localizedData} layout="vertical" barSize={16}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" />
            <XAxis
              type="number"
              fontSize={12}
              stroke="oklch(1 0 0 / 40%)"
              allowDecimals={false}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={100}
              fontSize={12}
              stroke="oklch(1 0 0 / 40%)"
            />
            <Tooltip
              formatter={(value: number) => [value, "次數"]}
              contentStyle={{
                background: "oklch(0.14 0.02 250)",
                border: "1px solid oklch(0.75 0.15 195 / 20%)",
                borderRadius: "8px",
              }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {localizedData.map((_, index) => (
                <Cell
                  key={index}
                  fill={BAR_COLORS[index % BAR_COLORS.length]}
                  fillOpacity={0.85}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
