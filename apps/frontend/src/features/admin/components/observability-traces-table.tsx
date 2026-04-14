import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { useRAGTraces } from "@/hooks/queries/use-observability";
import { getToolLabel } from "@/constants/tool-labels";
import type { RAGTrace, RAGTraceStep } from "@/types/observability";

const PAGE_SIZE = 30;

function ElapsedBadge({ ms }: { ms: number }) {
  const color =
    ms >= 2000 ? "text-red-600 dark:text-red-400"
    : ms >= 500 ? "text-yellow-600 dark:text-yellow-400"
    : "text-green-600 dark:text-green-400";
  return <span className={`font-mono text-sm ${color}`}>{ms.toFixed(1)}</span>;
}

function StepDetail({ step, index }: { step: RAGTraceStep; index: number }) {
  const [showOutput, setShowOutput] = useState(false);
  const toolName = step.tool_name || step.name || "unknown";
  const label = getToolLabel(toolName);
  const iteration = step.iteration ?? index + 1;
  const hasOutput = !!step.tool_output;

  return (
    <div className="py-1 text-xs">
      <div className="flex items-center gap-3">
        <span className="w-6 text-right font-medium text-muted-foreground">
          {iteration}.
        </span>
        <span className="font-medium">{label}</span>
        {step.elapsed_ms != null && (
          <span className="font-mono text-muted-foreground">
            {step.elapsed_ms.toFixed(1)} ms
          </span>
        )}
        {step.reasoning && (
          <span className="truncate text-muted-foreground">
            {step.reasoning}
          </span>
        )}
        {step.tool_input && (
          <span className="truncate text-muted-foreground">
            {JSON.stringify(step.tool_input).slice(0, 80)}
          </span>
        )}
        {hasOutput && (
          <button
            type="button"
            className="ml-auto flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
            onClick={(e) => { e.stopPropagation(); setShowOutput(!showOutput); }}
          >
            {showOutput ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            Output
          </button>
        )}
      </div>
      {showOutput && step.tool_output && (
        <pre className="mt-1 ml-9 whitespace-pre-wrap rounded bg-muted/50 p-2 text-xs text-muted-foreground max-h-48 overflow-y-auto">
          {step.tool_output}
        </pre>
      )}
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

function PromptSnapshotBlock({ prompt }: { prompt: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-2 rounded-md border bg-muted/20 px-3 py-2">
      <button
        type="button"
        className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        System Prompt
      </button>
      {open && (
        <pre className="mt-2 whitespace-pre-wrap text-xs text-muted-foreground max-h-64 overflow-y-auto">
          {prompt}
        </pre>
      )}
    </div>
  );
}

function ExpandableTraceRow({ trace, tenantNameMap }: { trace: RAGTrace; tenantNameMap: Map<string, string> }) {
  const [expanded, setExpanded] = useState(false);
  const hasSteps = trace.steps && trace.steps.length > 0;
  const hasContent = hasSteps || !!trace.prompt_snapshot;
  return (
    <>
      <TableRow
        className={hasContent ? "cursor-pointer hover:bg-muted/50" : ""}
        onClick={() => hasContent && setExpanded(!expanded)}
      >
        <TableCell className="w-8">
          {hasContent && (expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />)}
        </TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">{formatTime(trace.created_at)}</TableCell>
        <TableCell className="text-xs">{tenantNameMap.get(trace.tenant_id) ?? trace.tenant_id.slice(0, 8)}</TableCell>
        <TableCell className="max-w-[300px] truncate text-sm" title={trace.query}>
          {trace.query.length > 60 ? trace.query.slice(0, 60) + "..." : trace.query}
        </TableCell>
        <TableCell className="text-center">
          <Badge variant="secondary">{trace.steps?.length ?? 0}</Badge>
        </TableCell>
        <TableCell className="text-center">{trace.chunk_count}</TableCell>
        <TableCell className="text-right"><ElapsedBadge ms={trace.total_ms} /></TableCell>
      </TableRow>
      {expanded && hasContent && (
        <TableRow>
          <TableCell />
          <TableCell colSpan={6}>
            <div className="rounded-md border bg-muted/30 px-4 py-2">
              {trace.prompt_snapshot && <PromptSnapshotBlock prompt={trace.prompt_snapshot} />}
              {hasSteps && trace.steps!.map((step, i) => <StepDetail key={i} step={step} index={i} />)}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function ObservabilityTracesTable() {
  const [page, setPage] = useState(0);
  const [tenantFilter, setTenantFilter] = useState<string | undefined>();
  const tenantNameMap = useTenantNameMap();

  const filters = {
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    tenant_id: tenantFilter,
  };
  const { data, isLoading } = useRAGTraces(filters);
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <AdminTenantFilter
          value={tenantFilter}
          onChange={(v) => { setTenantFilter(v); setPage(0); }}
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
              <TableHead>查詢</TableHead>
              <TableHead className="w-20 text-center">步驟</TableHead>
              <TableHead className="w-20 text-center">區塊</TableHead>
              <TableHead className="w-24 text-right">耗時</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} className="text-center py-8">載入中...</TableCell></TableRow>
            )}
            {data?.items.map((t) => <ExpandableTraceRow key={t.id} trace={t} tenantNameMap={tenantNameMap} />)}
            {data && data.items.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">沒有 RAG 追蹤記錄</TableCell></TableRow>
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
