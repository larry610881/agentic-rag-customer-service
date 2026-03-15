import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, ChevronDown, ChevronRight } from "lucide-react";
import {
  useErrorEvents,
  useResolveErrorEvent,
} from "@/hooks/queries/use-error-events";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ErrorEvent } from "@/types/error-event";

const PAGE_SIZE = 20;

function sourceBadgeVariant(
  source: string,
): "default" | "secondary" | "outline" | "destructive" {
  switch (source) {
    case "backend":
      return "destructive";
    case "frontend":
      return "default";
    case "widget":
      return "secondary";
    default:
      return "outline";
  }
}

function ErrorEventDetail({ event }: { event: ErrorEvent }) {
  return (
    <div className="space-y-3 rounded-md bg-muted/30 p-4 text-sm">
      {event.stack_trace && (
        <div>
          <p className="font-medium mb-1">Stack Trace</p>
          <pre className="whitespace-pre-wrap text-xs font-mono bg-muted p-2 rounded max-h-60 overflow-auto">
            {event.stack_trace}
          </pre>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-muted-foreground">Fingerprint: </span>
          <span className="font-mono">{event.fingerprint}</span>
        </div>
        {event.request_id && (
          <div>
            <span className="text-muted-foreground">Request ID: </span>
            <span className="font-mono">{event.request_id}</span>
          </div>
        )}
        {event.method && (
          <div>
            <span className="text-muted-foreground">Method: </span>
            {event.method}
          </div>
        )}
        {event.status_code && (
          <div>
            <span className="text-muted-foreground">Status: </span>
            {event.status_code}
          </div>
        )}
        {event.tenant_id && (
          <div>
            <span className="text-muted-foreground">Tenant: </span>
            <span className="font-mono">{event.tenant_id}</span>
          </div>
        )}
        {event.user_agent && (
          <div className="col-span-2">
            <span className="text-muted-foreground">User Agent: </span>
            <span className="break-all">{event.user_agent}</span>
          </div>
        )}
      </div>
      {event.extra && Object.keys(event.extra).length > 0 && (
        <div>
          <p className="font-medium mb-1">Extra</p>
          <pre className="whitespace-pre-wrap text-xs font-mono bg-muted p-2 rounded max-h-40 overflow-auto">
            {JSON.stringify(event.extra, null, 2)}
          </pre>
        </div>
      )}
      {event.resolved && (
        <div className="text-xs text-muted-foreground">
          Resolved at {event.resolved_at} by {event.resolved_by}
        </div>
      )}
    </div>
  );
}

export default function AdminErrorEventsPage() {
  const [source, setSource] = useState("all");
  const [resolved, setResolved] = useState("all");
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useErrorEvents({
    source,
    resolved,
    limit: PAGE_SIZE,
    offset,
  });
  const resolveMutation = useResolveErrorEvent();

  const handleResolve = (id: string) => {
    resolveMutation.mutate(id, {
      onSuccess: () => toast.success("已標記為已解決"),
      onError: () => toast.error("操作失敗"),
    });
  };

  const events = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">錯誤追蹤</h1>
        <p className="text-muted-foreground">
          查看前端、後端與 Widget 的錯誤事件
        </p>
      </div>

      <div className="flex items-center gap-4">
        <Select value={source} onValueChange={(v) => { setSource(v); setOffset(0); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="來源" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部來源</SelectItem>
            <SelectItem value="backend">Backend</SelectItem>
            <SelectItem value="frontend">Frontend</SelectItem>
            <SelectItem value="widget">Widget</SelectItem>
          </SelectContent>
        </Select>

        <Select value={resolved} onValueChange={(v) => { setResolved(v); setOffset(0); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="狀態" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部狀態</SelectItem>
            <SelectItem value="false">未解決</SelectItem>
            <SelectItem value="true">已解決</SelectItem>
          </SelectContent>
        </Select>

        <span className="ml-auto text-sm text-muted-foreground">
          共 {total} 筆
        </span>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead className="w-24">來源</TableHead>
              <TableHead className="w-40">錯誤類型</TableHead>
              <TableHead>訊息</TableHead>
              <TableHead className="w-32">路徑</TableHead>
              <TableHead className="w-24">狀態</TableHead>
              <TableHead className="w-40">時間</TableHead>
              <TableHead className="w-24">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                  載入中...
                </TableCell>
              </TableRow>
            ) : events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                  無錯誤事件
                </TableCell>
              </TableRow>
            ) : (
              events.map((event) => (
                <TableRow key={event.id} className="group">
                  <TableCell>
                    <button
                      className="p-0.5 hover:bg-muted rounded"
                      onClick={() =>
                        setExpandedId(expandedId === event.id ? null : event.id)
                      }
                    >
                      {expandedId === event.id ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </button>
                  </TableCell>
                  <TableCell>
                    <Badge variant={sourceBadgeVariant(event.source)}>
                      {event.source}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {event.error_type}
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-sm">
                    {event.message}
                  </TableCell>
                  <TableCell className="font-mono text-xs truncate max-w-[8rem]">
                    {event.path}
                  </TableCell>
                  <TableCell>
                    <Badge variant={event.resolved ? "outline" : "destructive"}>
                      {event.resolved ? "已解決" : "未解決"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(event.created_at).toLocaleString("zh-TW")}
                  </TableCell>
                  <TableCell>
                    {!event.resolved && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleResolve(event.id)}
                        disabled={resolveMutation.isPending}
                      >
                        <CheckCircle2 className="h-4 w-4 mr-1" />
                        解決
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Expanded detail row rendered below the table */}
      {expandedId && events.find((e) => e.id === expandedId) && (
        <ErrorEventDetail
          event={events.find((e) => e.id === expandedId)!}
        />
      )}

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            上一頁
          </Button>
          <span className="text-sm text-muted-foreground">
            {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} / {total}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            下一頁
          </Button>
        </div>
      )}
    </div>
  );
}
