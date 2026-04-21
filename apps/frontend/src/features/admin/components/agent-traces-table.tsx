import { useState } from "react";
import { Copy } from "lucide-react";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { useAgentTraces } from "@/hooks/queries/use-agent-traces";
import type { AgentTraceFilters } from "@/hooks/queries/use-agent-traces";
import { formatDateTime } from "@/lib/format-date";
import { formatTraceShortId } from "@/lib/trace-id-format";
import type { AgentExecutionTrace } from "@/types/agent-trace";

const PAGE_SIZE = 30;

const MODE_LABELS: Record<string, string> = {
  react: "ReAct",
  supervisor: "Supervisor",
  meta_supervisor: "Meta",
};

const MODE_COLORS: Record<string, string> = {
  react: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  supervisor:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  meta_supervisor:
    "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
};

const OUTCOME_BADGE_CLASS: Record<string, string> = {
  success: "bg-emerald-500/15 text-emerald-700",
  failed: "bg-destructive/15 text-destructive",
  partial: "bg-orange-500/15 text-orange-700",
};

const OUTCOME_ICON: Record<string, string> = {
  success: "✅",
  failed: "❌",
  partial: "⚠️",
};

function ElapsedBadge({ ms }: { ms: number }) {
  const color =
    ms >= 2000
      ? "text-red-600 dark:text-red-400"
      : ms >= 500
        ? "text-yellow-600 dark:text-yellow-400"
        : "text-green-600 dark:text-green-400";
  return <span className={`font-mono text-sm ${color}`}>{ms.toFixed(0)}</span>;
}

/** S-Gov.6a: Trace ID 短碼 cell — 顯示 trc_YYYYMMDD_xxxx + hover 顯示完整 UUID + 📋 複製 */
function TraceIdCell({ trace }: { trace: AgentExecutionTrace }) {
  const short = formatTraceShortId(trace.trace_id, trace.created_at);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(trace.trace_id);
            toast.success("已複製完整 Trace ID");
          }}
          className="font-mono text-xs hover:text-primary inline-flex items-center gap-1"
        >
          {short}
          <Copy className="h-3 w-3 opacity-40 hover:opacity-100" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">
        <p className="font-mono text-xs">{trace.trace_id}</p>
        <p className="text-xs text-muted-foreground">點擊複製</p>
      </TooltipContent>
    </Tooltip>
  );
}

type AgentTracesTableProps = {
  /** S-Gov.6a: filter 由外層管理；本元件只負責 page + render */
  filters: Omit<AgentTraceFilters, "limit" | "offset">;
  onSelectTrace: (trace: AgentExecutionTrace) => void;
};

export function AgentTracesTable({
  filters,
  onSelectTrace,
}: AgentTracesTableProps) {
  const [page, setPage] = useState(0);
  const tenantNameMap = useTenantNameMap();

  const { data, isLoading } = useAgentTraces({
    ...filters,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      {data && (
        <span className="text-sm text-muted-foreground">
          共 {data.total} 筆
        </span>
      )}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[180px]">Trace ID</TableHead>
              <TableHead className="w-40">時間</TableHead>
              <TableHead className="w-24">租戶</TableHead>
              <TableHead className="w-28">Agent 模式</TableHead>
              <TableHead className="w-24">Outcome</TableHead>
              <TableHead className="w-20">來源</TableHead>
              <TableHead className="w-36">模型</TableHead>
              <TableHead className="w-20 text-center">節點數</TableHead>
              <TableHead className="w-24 text-right">耗時 (ms)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={9} className="py-8 text-center">
                  載入中...
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((t) => (
              <TableRow
                key={t.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => onSelectTrace(t)}
              >
                <TableCell>
                  <TraceIdCell trace={t} />
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {formatDateTime(t.created_at)}
                </TableCell>
                <TableCell className="text-xs">
                  {tenantNameMap.get(t.tenant_id) ??
                    t.tenant_id.slice(0, 8)}
                </TableCell>
                <TableCell>
                  <Badge
                    variant="secondary"
                    className={MODE_COLORS[t.agent_mode] ?? ""}
                  >
                    {MODE_LABELS[t.agent_mode] ?? t.agent_mode}
                  </Badge>
                </TableCell>
                <TableCell>
                  {t.outcome ? (
                    <Badge className={OUTCOME_BADGE_CLASS[t.outcome] ?? ""}>
                      {OUTCOME_ICON[t.outcome] ?? ""} {t.outcome}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-xs">
                  {t.source === "line" ? "📱 LINE" : t.source === "widget" ? "💬 Widget" : t.source === "web" ? "🌐 Web" : t.source || "-"}
                </TableCell>
                <TableCell>
                  {t.llm_model ? (
                    <Badge variant="outline" className="max-w-[130px] truncate font-mono text-xs">
                      {t.llm_model}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-center">
                  <Badge variant="outline">{t.nodes?.length ?? 0}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <ElapsedBadge ms={t.total_ms} />
                </TableCell>
              </TableRow>
            ))}
            {data && data.items.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={9}
                  className="py-8 text-center text-muted-foreground"
                >
                  沒有 Agent 執行追蹤記錄
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            第 {page + 1} / {totalPages} 頁
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              上一頁
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              下一頁
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
