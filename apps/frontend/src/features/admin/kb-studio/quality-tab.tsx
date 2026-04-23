import { useState } from "react";
import { useKbChunks, useKbQualitySummary } from "@/hooks/queries/use-kb-chunks";
import type { Chunk } from "@/types/chunk";
import { cn } from "@/lib/utils";

interface QualityTabProps {
  kbId: string;
  onEditChunk?: (chunk: Chunk) => void;
}

export function QualityTab({ kbId, onEditChunk }: QualityTabProps) {
  const { data, isLoading, error } = useKbQualitySummary(kbId);
  const [pageSize] = useState(200);
  const { data: chunksPage, isLoading: chunksLoading } = useKbChunks({
    kbId,
    page: 1,
    pageSize,
  });

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

  const lowChunks = (chunksPage?.items ?? []).filter((c) => c.quality_flag);
  const hasMorePages = (chunksPage?.total ?? 0) > pageSize;

  const flagCounts = lowChunks.reduce<Record<string, number>>((acc, c) => {
    const key = c.quality_flag ?? "other";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
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

      {Object.keys(flagCounts).length > 0 && (
        <section>
          <h3 className="text-sm font-semibold mb-2">品質 flag 分布（前 {pageSize} 筆取樣）</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(flagCounts).map(([flag, count]) => (
              <FlagBadge key={flag} flag={flag} count={count} />
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">低品質 chunk 列表</h3>
          {hasMorePages && (
            <span className="text-xs text-muted-foreground">
              僅顯示前 {pageSize} 筆（全 KB 共 {chunksPage?.total} chunks）
            </span>
          )}
        </div>
        {chunksLoading ? (
          <p className="text-muted-foreground text-sm">載入 chunk 清單中...</p>
        ) : lowChunks.length === 0 ? (
          <p className="text-muted-foreground text-sm">取樣範圍無低品質 chunk</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {lowChunks.map((c) => (
              <li
                key={c.id}
                className="flex items-start gap-3 px-3 py-2 text-sm hover:bg-muted/40 transition-colors"
              >
                <FlagBadge flag={c.quality_flag ?? "other"} compact />
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs text-muted-foreground truncate">
                    {c.id}
                  </div>
                  <div className="line-clamp-2 text-xs mt-0.5">
                    {c.content || "(空內容)"}
                  </div>
                </div>
                {onEditChunk && (
                  <button
                    type="button"
                    onClick={() => onEditChunk(c)}
                    className="text-xs text-primary hover:underline shrink-0"
                  >
                    編輯
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
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
        className={cn(
          "text-2xl font-bold",
          accent === "warn" && "text-amber-600",
        )}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function FlagBadge({
  flag,
  count,
  compact = false,
}: {
  flag: string;
  count?: number;
  compact?: boolean;
}) {
  const labels: Record<string, string> = {
    too_short: "過短",
    incomplete: "不完整",
    low_cohesion: "低聚合",
    other: "其他",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium",
        "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
        compact && "px-1.5",
      )}
    >
      {labels[flag] ?? flag}
      {typeof count === "number" && (
        <span className="text-[10px] opacity-70">×{count}</span>
      )}
    </span>
  );
}
