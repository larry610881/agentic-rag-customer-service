import { useState } from "react";
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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import type { RequestLogItem, TraceStep } from "@/hooks/queries/use-logs";
import { useRequestLogs } from "@/hooks/queries/use-logs";

const PAGE_SIZE = 30;

function StatusBadge({ code }: { code: number }) {
  const variant =
    code >= 500
      ? "destructive"
      : code >= 400
        ? "outline"
        : "secondary";
  return <Badge variant={variant}>{code}</Badge>;
}

function ElapsedBadge({ ms }: { ms: number }) {
  const color =
    ms >= 2000
      ? "text-red-600 dark:text-red-400"
      : ms >= 500
        ? "text-yellow-600 dark:text-yellow-400"
        : "text-green-600 dark:text-green-400";
  return <span className={`font-mono text-sm ${color}`}>{ms.toFixed(1)}</span>;
}

function TraceStepRow({ step }: { step: TraceStep }) {
  return (
    <div className="flex items-center gap-3 py-1 font-mono text-xs">
      <span className="w-20 text-right text-muted-foreground">
        {step.elapsed_ms.toFixed(1)} ms
      </span>
      <span className="font-medium">{step.step}</span>
      {step.sql && (
        <span className="truncate text-muted-foreground" title={step.sql}>
          {step.sql}
        </span>
      )}
    </div>
  );
}

function ExpandableRow({
  log,
  tenantNameMap,
}: {
  log: RequestLogItem;
  tenantNameMap: Map<string, string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasSteps = log.trace_steps && log.trace_steps.length > 0;
  const hasError = !!log.error_detail;
  const hasContent = hasSteps || hasError;

  return (
    <>
      <TableRow
        className={hasContent ? "cursor-pointer hover:bg-muted/50" : ""}
        onClick={() => hasContent && setExpanded(!expanded)}
      >
        <TableCell className="w-8">
          {hasContent &&
            (expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            ))}
        </TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">
          {formatTime(log.created_at)}
        </TableCell>
        <TableCell className="text-xs">
          {log.tenant_id
            ? tenantNameMap.get(log.tenant_id) ?? log.tenant_id.slice(0, 8)
            : "-"}
        </TableCell>
        <TableCell className="font-mono text-xs">{log.request_id}</TableCell>
        <TableCell>
          <span className="font-mono text-xs">
            <span className="font-semibold">{log.method}</span>{" "}
            <span className="text-muted-foreground">{log.path}</span>
          </span>
        </TableCell>
        <TableCell>
          <StatusBadge code={log.status_code} />
        </TableCell>
        <TableCell className="text-right">
          <ElapsedBadge ms={log.elapsed_ms} />
        </TableCell>
      </TableRow>
      {expanded && hasContent && (
        <TableRow>
          <TableCell />
          <TableCell colSpan={6}>
            <div className="rounded-md border bg-muted/30 px-4 py-2 space-y-2">
              {hasError && (
                <div className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2">
                  <span className="text-xs font-medium text-destructive">Error Detail</span>
                  <pre className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground max-h-32 overflow-y-auto">
                    {log.error_detail}
                  </pre>
                </div>
              )}
              {hasSteps &&
                log.trace_steps!.map((step, i) => (
                  <TraceStepRow key={i} step={step} />
                ))}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function RequestLogsTable() {
  const [page, setPage] = useState(0);
  const [pathFilter, setPathFilter] = useState("");
  const [minMs, setMinMs] = useState("");
  const [tenantFilter, setTenantFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const tenantNameMap = useTenantNameMap();

  const filters = {
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    path: pathFilter || undefined,
    min_elapsed_ms: minMs ? Number(minMs) : undefined,
    tenant_id: tenantFilter,
    status_range: statusFilter || undefined,
    method: methodFilter || undefined,
  };

  const { data, isLoading } = useRequestLogs(filters);

  // Client-side status code range filtering (backend only supports exact match)
  const filteredItems = data?.items.filter((log) => {
    if (!statusFilter) return true;
    const prefix = Math.floor(log.status_code / 100);
    return statusFilter === `${prefix}xx`;
  });

  const displayTotal = statusFilter ? (filteredItems?.length ?? 0) : (data?.total ?? 0);
  const totalPages = statusFilter
    ? Math.ceil(displayTotal / PAGE_SIZE)
    : data
      ? Math.ceil(data.total / PAGE_SIZE)
      : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <AdminTenantFilter
          value={tenantFilter}
          onChange={(v) => {
            setTenantFilter(v);
            setPage(0);
          }}
        />
        <Select
          value={methodFilter || "all"}
          onValueChange={(v) => {
            setMethodFilter(v === "all" ? "" : v);
            setPage(0);
          }}
        >
          <SelectTrigger className="w-[120px]">
            <SelectValue placeholder="Method" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部 Method</SelectItem>
            <SelectItem value="GET">GET</SelectItem>
            <SelectItem value="POST">POST</SelectItem>
            <SelectItem value="PUT">PUT</SelectItem>
            <SelectItem value="PATCH">PATCH</SelectItem>
            <SelectItem value="DELETE">DELETE</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={statusFilter || "all"}
          onValueChange={(v) => {
            setStatusFilter(v === "all" ? "" : v);
            setPage(0);
          }}
        >
          <SelectTrigger className="w-[120px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部 Status</SelectItem>
            <SelectItem value="2xx">2xx</SelectItem>
            <SelectItem value="3xx">3xx</SelectItem>
            <SelectItem value="4xx">4xx</SelectItem>
            <SelectItem value="5xx">5xx</SelectItem>
          </SelectContent>
        </Select>
        <Input
          placeholder="篩選 API path..."
          value={pathFilter}
          onChange={(e) => {
            setPathFilter(e.target.value);
            setPage(0);
          }}
          className="w-64"
        />
        <Input
          placeholder="最低耗時 (ms)"
          type="number"
          value={minMs}
          onChange={(e) => {
            setMinMs(e.target.value);
            setPage(0);
          }}
          className="w-36"
        />
        {data && (
          <span className="text-sm text-muted-foreground">
            共 {displayTotal} 筆
          </span>
        )}
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead className="w-40">時間</TableHead>
              <TableHead className="w-24">租戶</TableHead>
              <TableHead className="w-32">Request ID</TableHead>
              <TableHead>API</TableHead>
              <TableHead className="w-20">Status</TableHead>
              <TableHead className="w-24 text-right">耗時</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  載入中...
                </TableCell>
              </TableRow>
            )}
            {filteredItems?.map((log) => (
              <ExpandableRow
                key={log.id}
                log={log}
                tenantNameMap={tenantNameMap}
              />
            ))}
            {data && (filteredItems?.length ?? 0) === 0 && (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="text-center py-8 text-muted-foreground"
                >
                  沒有符合條件的記錄
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
