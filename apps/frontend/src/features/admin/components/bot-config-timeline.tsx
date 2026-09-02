/** Issue #60 — Bot 生效設定時間軸：hash 列表 + 勾選兩筆比較差異 */

import { GitCompare } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/format-date";
import {
  useBotConfigTimeline,
  useConfigSnapshotDiff,
} from "@/hooks/queries/use-config-snapshots";
import { ConfigDiffTable } from "./config-diff-table";
import { ConfigHashChip } from "./config-hash-chip";

interface BotConfigTimelineProps {
  botId: string;
  limit?: number;
}

export function BotConfigTimeline({ botId, limit = 50 }: BotConfigTimelineProps) {
  const { data, isLoading, error } = useBotConfigTimeline(botId, limit);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparePair, setComparePair] = useState<[string, string] | null>(null);

  const diffQuery = useConfigSnapshotDiff(
    comparePair?.[0],
    comparePair?.[1],
    !!comparePair,
  );

  const toggle = (hash: string, checked: boolean) => {
    setSelected((prev) => {
      if (checked) {
        if (prev.includes(hash)) return prev;
        // 最多兩筆：超過時丟掉最早勾的那筆
        return prev.length >= 2 ? [prev[1], hash] : [...prev, hash];
      }
      return prev.filter((h) => h !== hash);
    });
  };

  const handleCompare = () => {
    if (selected.length !== 2) return;
    const items = data?.items ?? [];
    // 時間軸為最新在前；比較時以較舊者為 a、較新者為 b（變更前 → 變更後）
    const idxA = items.findIndex((i) => i.hash === selected[0]);
    const idxB = items.findIndex((i) => i.hash === selected[1]);
    const [older, newer] = idxA > idxB ? [selected[0], selected[1]] : [selected[1], selected[0]];
    setComparePair([older, newer]);
  };

  if (isLoading) {
    return <Skeleton className="h-40 w-full" data-testid="timeline-loading" />;
  }

  if (error) {
    return (
      <p className="text-sm text-destructive">
        載入設定時間軸失敗：{(error as Error).message}
      </p>
    );
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="timeline-empty">
        尚無生效設定紀錄——此 bot 完成第一輪對話後會自動出現。
      </p>
    );
  }

  return (
    <div className="space-y-4" data-testid="bot-config-timeline">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm text-muted-foreground">
          共 {items.length} 個不同設定版本（最新在前）。勾選兩筆後可比較差異。
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="ml-auto"
          disabled={selected.length !== 2}
          onClick={handleCompare}
        >
          <GitCompare className="mr-1 h-4 w-4" />
          比較
        </Button>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10" />
              <TableHead>設定 hash</TableHead>
              <TableHead>首次生效</TableHead>
              <TableHead>最後生效</TableHead>
              <TableHead className="text-right">對話輪數</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const checked = selected.includes(item.hash);
              return (
                <TableRow key={item.hash} data-testid={`timeline-row-${item.hash}`}>
                  <TableCell>
                    <Checkbox
                      aria-label={`選取 ${item.hash}`}
                      checked={checked}
                      onCheckedChange={(v) => toggle(item.hash, v === true)}
                    />
                  </TableCell>
                  <TableCell>
                    <ConfigHashChip hash={item.hash} copyable />
                  </TableCell>
                  <TableCell className="text-sm">
                    {formatDateTime(item.first_seen_at)}
                  </TableCell>
                  <TableCell className="text-sm">
                    {formatDateTime(item.last_seen_at)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {item.turns}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {comparePair && (
        <div className="space-y-2" data-testid="timeline-diff">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted-foreground">比較</span>
            <ConfigHashChip hash={comparePair[0]} />
            <span className="text-muted-foreground">→</span>
            <ConfigHashChip hash={comparePair[1]} />
          </div>
          {diffQuery.isLoading && <Skeleton className="h-24 w-full" />}
          {diffQuery.error && (
            <p className="text-sm text-destructive">
              載入差異失敗：{(diffQuery.error as Error).message}
            </p>
          )}
          {diffQuery.data && (
            <ConfigDiffTable changedFields={diffQuery.data.changed_fields} />
          )}
        </div>
      )}
    </div>
  );
}
