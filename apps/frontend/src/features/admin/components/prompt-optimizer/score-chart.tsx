import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CHART_TOOLTIP } from "@/lib/chart-styles";

interface ScoreChartProps {
  data: { iteration: number; score: number; bestScore: number }[];
  baselineScore?: number;
}

export function ScoreChart({ data, baselineScore }: ScoreChartProps) {
  if (!data.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Score Trend</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-12 text-center text-muted-foreground">
            尚無評分資料
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Score Trend</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="oklch(1 0 0 / 5%)"
            />
            <XAxis
              dataKey="iteration"
              fontSize={12}
              stroke="oklch(1 0 0 / 40%)"
              label={{
                value: "Iteration",
                position: "insideBottom",
                offset: -5,
                fontSize: 12,
              }}
            />
            <YAxis
              fontSize={12}
              stroke="oklch(1 0 0 / 40%)"
              domain={[0, 1]}
            />
            <Tooltip
              {...CHART_TOOLTIP}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any, name: any) => [
                Number(value).toFixed(3),
                name === "score" ? "Current Score" : "Best Score",
              ]}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="var(--chart-hex-1)"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="score"
            />
            <Line
              type="monotone"
              dataKey="bestScore"
              stroke="var(--chart-hex-2)"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              name="bestScore"
            />
            {baselineScore !== undefined && (
              <ReferenceLine
                y={baselineScore}
                stroke="oklch(0.7 0.15 30)"
                strokeDasharray="4 4"
                label={{
                  value: `Baseline: ${baselineScore.toFixed(3)}`,
                  position: "right",
                  fontSize: 11,
                  fill: "oklch(0.7 0.15 30)",
                }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
