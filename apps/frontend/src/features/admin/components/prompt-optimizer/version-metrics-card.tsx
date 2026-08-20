/** Issue #54 §13.6 — 版本服役成效卡（方向性參考，非嚴格因果） */

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useVersionMetrics } from "@/hooks/queries/use-config-versions";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}

export function VersionMetricsCard({
  botId,
  versionId,
}: {
  botId: string;
  versionId: string;
}) {
  const { data: m, isLoading } = useVersionMetrics(botId, versionId);

  if (isLoading) {
    return <Skeleton className="h-24 w-full" />;
  }
  if (!m) return null;
  if (m.message_count === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        此版本服役期間尚無對話數據。
      </p>
    );
  }

  return (
    <Card className="p-3">
      <div className="mb-2 text-xs font-medium text-muted-foreground">
        服役成效（前後對照含流量組成差異，僅供方向性參考）
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="對話則數" value={String(m.message_count)} />
        <Stat
          label="平均延遲"
          value={m.avg_latency_ms != null ? `${m.avg_latency_ms}ms` : "—"}
        />
        <Stat
          label="總成本"
          value={`$${m.total_cost.toFixed(4)}`}
        />
        <Stat
          label="正評率"
          value={
            m.feedback_positive_rate != null
              ? `${(m.feedback_positive_rate * 100).toFixed(0)}%（${m.feedback_up}👍/${m.feedback_down}👎）`
              : "無回饋"
          }
        />
        {Object.entries(m.eval_avg_by_layer).map(([layer, score]) => (
          <Stat
            key={layer}
            label={`線上評分 ${layer}`}
            value={score.toFixed(3)}
          />
        ))}
      </div>
    </Card>
  );
}
