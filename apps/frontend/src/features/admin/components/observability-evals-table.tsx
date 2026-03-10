import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useRAGEvals } from "@/hooks/queries/use-observability";
import type { EvalResult, EvalDimension, ChunkScore } from "@/types/observability";

const PAGE_SIZE = 30;

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 0.8 ? "text-green-600 dark:text-green-400"
    : score >= 0.5 ? "text-yellow-600 dark:text-yellow-400"
    : "text-red-600 dark:text-red-400";
  return <span className={`font-mono text-sm font-semibold ${color}`}>{score.toFixed(2)}</span>;
}

function ChunkScoreBadge({ score }: { score: number }) {
  const color =
    score >= 0.7 ? "text-green-600 dark:text-green-400"
    : score >= 0.4 ? "text-yellow-600 dark:text-yellow-400"
    : "text-red-600 dark:text-red-400";
  return <span className={`font-mono text-xs font-semibold ${color}`}>{score.toFixed(2)}</span>;
}

function ChunkScoreList({ scores }: { scores: ChunkScore[] }) {
  return (
    <div className="mt-1 ml-16 space-y-0.5 border-l-2 border-muted pl-3">
      {scores.map((cs) => {
        const numScore = Number(cs.score) || 0;
        return (
          <div key={cs.index} className="flex items-center gap-2 text-xs">
            <span className="w-6 text-right font-mono text-muted-foreground">[{cs.index}]</span>
            <ChunkScoreBadge score={numScore} />
            <span className="text-muted-foreground">{cs.reason}</span>
          </div>
        );
      })}
    </div>
  );
}

function DimensionDetail({ dim }: { dim: EvalDimension }) {
  const chunkScores = dim.metadata?.chunk_scores;
  return (
    <div className="py-1 text-xs">
      <div className="flex items-start gap-3">
        <span className="w-16 text-right font-mono"><ScoreBadge score={dim.score} /></span>
        <span className="font-medium w-40">{dim.name}</span>
        <span className="text-muted-foreground flex-1">{dim.explanation}</span>
      </div>
      {chunkScores && chunkScores.length > 0 && <ChunkScoreList scores={chunkScores} />}
    </div>
  );
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("zh-TW", {
    month: "2-digit", day: "2-digit", hour: "2-digit",
    minute: "2-digit", second: "2-digit", hour12: false,
  });
}

function ExpandableEvalRow({ eval: ev }: { eval: EvalResult }) {
  const [expanded, setExpanded] = useState(false);
  const hasDims = ev.dimensions && ev.dimensions.length > 0;
  return (
    <>
      <TableRow
        className={hasDims ? "cursor-pointer hover:bg-muted/50" : ""}
        onClick={() => hasDims && setExpanded(!expanded)}
      >
        <TableCell className="w-8">
          {hasDims && (expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />)}
        </TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">{formatTime(ev.created_at)}</TableCell>
        <TableCell className="font-mono text-xs">{ev.tenant_id.slice(0, 8)}</TableCell>
        <TableCell><Badge variant="outline">{ev.layer}</Badge></TableCell>
        <TableCell><ScoreBadge score={ev.avg_score} /></TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">{ev.model_used}</TableCell>
        <TableCell className="text-center">
          <Badge variant="secondary">{ev.dimensions?.length ?? 0}</Badge>
        </TableCell>
      </TableRow>
      {expanded && hasDims && (
        <TableRow>
          <TableCell />
          <TableCell colSpan={6}>
            <div className="rounded-md border bg-muted/30 px-4 py-2">
              {ev.dimensions!.map((dim, i) => <DimensionDetail key={i} dim={dim} />)}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function ObservabilityEvalsTable() {
  const [page, setPage] = useState(0);
  const [tenantFilter, setTenantFilter] = useState("");
  const [layerFilter, setLayerFilter] = useState("");
  const [minScore, setMinScore] = useState("");

  const filters = {
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    tenant_id: tenantFilter || undefined,
    layer: layerFilter || undefined,
    min_score: minScore ? Number(minScore) : undefined,
  };
  const { data, isLoading } = useRAGEvals(filters);
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="篩選 Tenant ID..."
          value={tenantFilter}
          onChange={(e) => { setTenantFilter(e.target.value); setPage(0); }}
          className="w-64"
        />
        <Select value={layerFilter} onValueChange={(v) => { setLayerFilter(v === "all" ? "" : v); setPage(0); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="Layer" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            <SelectItem value="L1">L1</SelectItem>
            <SelectItem value="L1+L2">L1+L2</SelectItem>
            <SelectItem value="L1+L2+L3">L1+L2+L3</SelectItem>
          </SelectContent>
        </Select>
        <Input
          placeholder="最低分數 (0-1)"
          type="number"
          step="0.1"
          min="0"
          max="1"
          value={minScore}
          onChange={(e) => { setMinScore(e.target.value); setPage(0); }}
          className="w-36"
        />
        {data && <span className="text-sm text-muted-foreground">共 {data.total} 筆</span>}
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead className="w-40">時間</TableHead>
              <TableHead className="w-24">Tenant</TableHead>
              <TableHead className="w-24">Layer</TableHead>
              <TableHead className="w-24">Avg Score</TableHead>
              <TableHead>Model</TableHead>
              <TableHead className="w-24 text-center">Dimensions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} className="text-center py-8">載入中...</TableCell></TableRow>
            )}
            {data?.items.map((ev) => <ExpandableEvalRow key={ev.id} eval={ev} />)}
            {data && data.items.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">沒有評估記錄</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">第 {page + 1} / {totalPages} 頁</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>上一頁</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>下一頁</Button>
          </div>
        </div>
      )}
    </div>
  );
}
