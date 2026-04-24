import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, Pencil } from "lucide-react";
import { formatDateTime } from "@/lib/format-date";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { useRAGEvals } from "@/hooks/queries/use-observability";
import type { EvalResult, EvalDimension, ChunkScore, DiagnosticHint } from "@/types/observability";

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
        const canJump = !!(cs.chunk_id && cs.kb_id);
        const isLowScore = numScore < 0.4;
        return (
          <div key={cs.index} className="flex items-center gap-2 text-xs">
            <span className="w-6 text-right font-mono text-muted-foreground">[{cs.index}]</span>
            <ChunkScoreBadge score={numScore} />
            <span className="text-muted-foreground flex-1">{cs.reason}</span>
            {canJump && (
              <Link
                to={`/admin/kb-studio/${cs.kb_id}?tab=chunks&highlight=${cs.chunk_id}`}
                className={
                  "inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] hover:bg-muted transition-colors " +
                  (isLowScore
                    ? "border-amber-500/50 text-amber-700 dark:text-amber-400"
                    : "border-muted text-muted-foreground")
                }
                title="到 KB Studio 編輯此 chunk"
              >
                <Pencil className="h-2.5 w-2.5" />
                修正
              </Link>
            )}
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

const HINT_COLORS: Record<string, string> = {
  critical: "border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-400",
  warning: "border-yellow-500/50 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
  info: "border-blue-500/50 bg-blue-500/10 text-blue-700 dark:text-blue-400",
};

const HINT_LABELS: Record<string, string> = {
  data_source: "資料源",
  rag_strategy: "RAG 策略",
  prompt: "Prompt",
  agent: "Agent",
};

function HintBadge({ hint }: { hint: DiagnosticHint }) {
  return (
    <div className={`rounded-md border px-3 py-2 text-xs ${HINT_COLORS[hint.severity] ?? ""}`}>
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-[10px]">
          {HINT_LABELS[hint.category] ?? hint.category}
        </Badge>
        <span className="font-medium">{hint.message}</span>
      </div>
      <p className="mt-1 text-muted-foreground">{hint.suggestion}</p>
    </div>
  );
}


function ExpandableEvalRow({ eval: ev, tenantNameMap }: { eval: EvalResult; tenantNameMap: Map<string, string> }) {
  const [expanded, setExpanded] = useState(false);
  const hasDims = ev.dimensions && ev.dimensions.length > 0;
  const hints = ev.diagnostic_hints ?? [];
  const hasContent = hasDims || hints.length > 0;
  return (
    <>
      <TableRow
        className={hasContent ? "cursor-pointer hover:bg-muted/50" : ""}
        onClick={() => hasContent && setExpanded(!expanded)}
      >
        <TableCell className="w-8">
          {hasContent && (expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />)}
        </TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">{formatDateTime(ev.created_at)}</TableCell>
        <TableCell className="text-xs">{tenantNameMap.get(ev.tenant_id) ?? ev.tenant_id.slice(0, 8)}</TableCell>
        <TableCell><Badge variant="outline">{ev.layer}</Badge></TableCell>
        <TableCell><ScoreBadge score={ev.avg_score} /></TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">{ev.model_used}</TableCell>
        <TableCell className="text-center">
          <Badge variant="secondary">{ev.dimensions?.length ?? 0}</Badge>
        </TableCell>
      </TableRow>
      {expanded && hasContent && (
        <TableRow>
          <TableCell />
          <TableCell colSpan={6}>
            <div className="rounded-md border bg-muted/30 px-4 py-2">
              {hasDims && ev.dimensions!.map((dim, i) => <DimensionDetail key={i} dim={dim} />)}
              {hints.length > 0 && (
                <div className="mt-3 space-y-2 border-t pt-3">
                  <span className="text-xs font-medium text-muted-foreground">診斷提示</span>
                  {hints.map((hint, i) => <HintBadge key={i} hint={hint} />)}
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function ObservabilityEvalsTable() {
  const [page, setPage] = useState(0);
  const [tenantFilter, setTenantFilter] = useState<string | undefined>();
  const [layerFilter, setLayerFilter] = useState("");
  const [minScore, setMinScore] = useState("");
  const tenantNameMap = useTenantNameMap();

  const filters = {
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    tenant_id: tenantFilter,
    layer: layerFilter || undefined,
    min_score: minScore ? Number(minScore) : undefined,
  };
  const { data, isLoading } = useRAGEvals(filters);
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <AdminTenantFilter
          value={tenantFilter}
          onChange={(v) => { setTenantFilter(v); setPage(0); }}
        />
        <Select value={layerFilter} onValueChange={(v) => { setLayerFilter(v === "all" ? "" : v); setPage(0); }}>
          <SelectTrigger className="w-36"><SelectValue placeholder="評估層級" /></SelectTrigger>
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
              <TableHead className="w-24">租戶</TableHead>
              <TableHead className="w-24">層級</TableHead>
              <TableHead className="w-24">平均分數</TableHead>
              <TableHead>模型</TableHead>
              <TableHead className="w-24 text-center">維度</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} className="text-center py-8">載入中...</TableCell></TableRow>
            )}
            {data?.items.map((ev) => <ExpandableEvalRow key={ev.id} eval={ev} tenantNameMap={tenantNameMap} />)}
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
