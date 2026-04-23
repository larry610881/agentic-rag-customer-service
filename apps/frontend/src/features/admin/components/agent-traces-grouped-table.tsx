import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { useAgentTracesGrouped } from "@/hooks/queries/use-agent-traces";
import { formatDateTime } from "@/lib/format-date";
import { formatTraceShortId } from "@/lib/trace-id-format";
import type {
  AgentExecutionTrace,
  ConversationTraceGroup,
} from "@/types/agent-trace";
import type { AgentTraceFilters } from "@/hooks/queries/use-agent-traces";

const PAGE_SIZE = 20;

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

interface GroupedTableProps {
  filters: Omit<AgentTraceFilters, "limit" | "offset">;
  onSelectTrace: (trace: AgentExecutionTrace) => void;
}

export function AgentTracesGroupedTable({
  filters,
  onSelectTrace,
}: GroupedTableProps) {
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const tenantNameMap = useTenantNameMap();

  const { data, isLoading, isError } = useAgentTracesGrouped({
    ...filters,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const toggle = (cid: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(cid)) next.delete(cid);
      else next.add(cid);
      return next;
    });
  };

  const groups = (data?.items ?? []) as ConversationTraceGroup[];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8" />
            <TableHead className="min-w-[320px]">對話內容</TableHead>
            <TableHead className="w-20">Trace 數</TableHead>
            <TableHead>Outcome 分布</TableHead>
            <TableHead>時間範圍</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isError ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center py-8 text-destructive">
                載入失敗
              </TableCell>
            </TableRow>
          ) : isLoading ? (
            <TableRow>
              <TableCell colSpan={5} className="py-3">
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              </TableCell>
            </TableRow>
          ) : groups.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center py-12 text-muted-foreground">
                目前無對話聚合資料
              </TableCell>
            </TableRow>
          ) : (
            groups.map((g) => {
              const isOpen = expanded.has(g.conversation_id);
              const outcomeCount = g.traces.reduce<Record<string, number>>(
                (acc, t) => {
                  const o = t.outcome ?? "success";
                  acc[o] = (acc[o] ?? 0) + 1;
                  return acc;
                },
                {},
              );
              const tenantName =
                tenantNameMap.get(g.traces[0]?.tenant_id ?? "") ?? "—";
              return (
                <Fragment key={g.conversation_id}>
                  <TableRow
                    className="cursor-pointer hover:bg-muted/40"
                    onClick={() => toggle(g.conversation_id)}
                  >
                    <TableCell>
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      <div className="flex flex-col gap-0.5">
                        {g.first_user_message ? (
                          <span className="line-clamp-1 font-medium">
                            <span className="text-muted-foreground mr-1">👤</span>
                            {g.first_user_message}
                          </span>
                        ) : (
                          <span className="text-muted-foreground italic">
                            （無使用者訊息）
                          </span>
                        )}
                        {g.last_assistant_answer && (
                          <span className="line-clamp-1 text-xs text-muted-foreground">
                            <span className="mr-1">🤖</span>
                            {g.last_assistant_answer}
                          </span>
                        )}
                        {g.summary && (
                          <span className="line-clamp-1 text-xs text-primary/80">
                            📝 {g.summary}
                          </span>
                        )}
                        <span className="font-mono text-[10px] text-muted-foreground/70">
                          {g.conversation_id.substring(0, 8)}… · {tenantName}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono">{g.trace_count}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {Object.entries(outcomeCount).map(([k, v]) => (
                          <Badge
                            key={k}
                            className={OUTCOME_BADGE_CLASS[k] ?? ""}
                          >
                            {OUTCOME_ICON[k] ?? ""} {v}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(g.first_at)}
                      <br />~ {formatDateTime(g.last_at)}
                    </TableCell>
                  </TableRow>
                  {isOpen && (
                    <TableRow>
                      <TableCell colSpan={5} className="bg-muted/20 p-0">
                        <div className="space-y-2 p-3">
                          {g.traces.map((t) => (
                            <button
                              key={t.id}
                              type="button"
                              onClick={() => onSelectTrace(t)}
                              className="flex w-full items-center justify-between rounded-md border bg-background p-2 text-left text-sm hover:bg-muted/50 transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                <span className="font-mono text-xs">
                                  {formatTraceShortId(t.trace_id, t.created_at)}
                                </span>
                                <Badge variant="outline" className="text-xs">
                                  {t.agent_mode}
                                </Badge>
                                {t.outcome && (
                                  <Badge
                                    className={
                                      OUTCOME_BADGE_CLASS[t.outcome] ?? ""
                                    }
                                  >
                                    {OUTCOME_ICON[t.outcome] ?? ""} {t.outcome}
                                  </Badge>
                                )}
                                <span className="text-xs text-muted-foreground">
                                  {t.total_ms.toFixed(0)} ms
                                </span>
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {formatDateTime(t.created_at)}
                              </span>
                            </button>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })
          )}
        </TableBody>
      </Table>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 border-t p-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage(Math.max(0, page - 1))}
          >
            上一頁
          </Button>
          <span className="text-sm text-muted-foreground">
            {page + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            下一頁
          </Button>
        </div>
      )}
    </div>
  );
}
