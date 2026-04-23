import { useKbQualitySummary } from "@/hooks/queries/use-kb-chunks";

interface QualityTabProps {
  kbId: string;
}

export function QualityTab({ kbId }: QualityTabProps) {
  const { data, isLoading, error } = useKbQualitySummary(kbId);

  if (isLoading) {
    return <p className="text-muted-foreground">載入中...</p>;
  }
  if (error) {
    return (
      <p className="text-destructive">
        載入失敗：{(error as Error).message}
      </p>
    );
  }
  if (!data) return null;

  const lowRatio = data.total_chunks
    ? data.low_quality_count / data.total_chunks
    : 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card label="總 chunks 數" value={data.total_chunks.toLocaleString()} />
      <Card
        label="低品質 chunks"
        value={data.low_quality_count.toLocaleString()}
        sub={`${(lowRatio * 100).toFixed(1)}%`}
        accent={lowRatio > 0.1 ? "warn" : "ok"}
      />
      <Card
        label="平均聚合度（粗估）"
        value={data.avg_cohesion_score.toFixed(4)}
        accent={data.avg_cohesion_score < 0.7 ? "warn" : "ok"}
      />
    </div>
  );
}

function Card({
  label,
  value,
  sub,
  accent = "ok",
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "ok" | "warn";
}) {
  return (
    <div className="rounded-md border p-4">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div
        className={
          accent === "warn"
            ? "text-2xl font-bold text-amber-600"
            : "text-2xl font-bold"
        }
      >
        {value}
      </div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}
