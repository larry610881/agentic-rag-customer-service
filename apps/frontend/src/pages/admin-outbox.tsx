import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import {
  useAbandonOutboxEvent,
  useBulkRetryOutbox,
  useOutboxDeadLetter,
  useOutboxStats,
  useRetryOutboxEvent,
} from "@/hooks/queries/use-outbox";
import type { OutboxEvent } from "@/types/outbox";

const EVENT_TYPE_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "vector.delete", label: "vector.delete" },
  { value: "vector.drop_collection", label: "vector.drop_collection" },
];

function formatAge(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

export default function AdminOutboxPage() {
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("all");
  const [tenantFilter, setTenantFilter] = useState<string>("");
  const [pendingAbandonId, setPendingAbandonId] = useState<string | null>(null);
  const [abandonReason, setAbandonReason] = useState<string>("");

  const stats = useOutboxStats();
  const filterParams = useMemo(
    () => ({
      event_type: eventTypeFilter === "all" ? undefined : eventTypeFilter,
      tenant_id: tenantFilter.trim() || undefined,
    }),
    [eventTypeFilter, tenantFilter],
  );
  const dlq = useOutboxDeadLetter(filterParams);
  const retry = useRetryOutboxEvent();
  const bulkRetry = useBulkRetryOutbox();
  const abandon = useAbandonOutboxEvent();

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">Outbox 死信佇列（DLQ）</h1>
        <p className="text-sm text-muted-foreground">
          PG ↔ Milvus 一致性事件，drain worker 連續失敗 8 次後進入此頁。
          一律 system_admin 才看得到。Stats 每 30 秒自動刷新。
        </p>
      </header>

      {/* Stats panel */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard
          label="Pending"
          value={stats.data?.pending_count}
          tone="muted"
        />
        <StatCard
          label="In progress"
          value={stats.data?.in_progress_count}
          tone="muted"
        />
        <StatCard
          label="DLQ (dead)"
          value={stats.data?.dead_count}
          tone={
            (stats.data?.dead_count ?? 0) > 0 ? "danger" : "muted"
          }
        />
        <StatCard
          label="最舊 pending 等待"
          value={
            stats.data?.oldest_pending_age_seconds === null
              ? "—"
              : stats.data?.oldest_pending_age_seconds !== undefined
                ? formatAge(stats.data.oldest_pending_age_seconds)
                : undefined
          }
          tone={
            (stats.data?.oldest_pending_age_seconds ?? 0) > 300
              ? "warning"
              : "muted"
          }
        />
      </section>

      {/* Filters + bulk actions */}
      <section className="rounded-md border bg-muted/20 p-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs">事件類型</Label>
            <Select
              value={eventTypeFilter}
              onValueChange={setEventTypeFilter}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EVENT_TYPE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="outbox-tenant-filter" className="text-xs">
              租戶 ID（可選）
            </Label>
            <Input
              id="outbox-tenant-filter"
              placeholder="留空 = 所有租戶"
              value={tenantFilter}
              onChange={(e) => setTenantFilter(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button
              type="button"
              variant="default"
              disabled={
                bulkRetry.isPending ||
                (dlq.data?.length ?? 0) === 0
              }
              onClick={() =>
                bulkRetry.mutate({
                  event_type: filterParams.event_type,
                  tenant_id: filterParams.tenant_id,
                  limit: 100,
                })
              }
            >
              批次重排（最多 100 筆）
            </Button>
          </div>
        </div>
      </section>

      {/* DLQ table */}
      {dlq.isLoading && (
        <p className="text-muted-foreground">載入 DLQ 中...</p>
      )}
      {dlq.error && (
        <p className="text-destructive">
          載入失敗：{(dlq.error as Error).message}
        </p>
      )}
      {!dlq.isLoading && dlq.data && (
        <DeadLetterTable
          events={dlq.data}
          onRetry={(id) => retry.mutate(id)}
          onAbandon={(id) => {
            setPendingAbandonId(id);
            setAbandonReason("");
          }}
          retryingId={retry.isPending ? retry.variables ?? null : null}
        />
      )}

      <ConfirmDangerDialog
        open={!!pendingAbandonId}
        onOpenChange={(o) => {
          if (!o) {
            setPendingAbandonId(null);
            setAbandonReason("");
          }
        }}
        title={`放棄事件「${pendingAbandonId ?? ""}」？`}
        description={
          <>
            <p>此操作會 <strong>永久刪除</strong> outbox row（hard delete），
            外部系統將不會再被同步。請確認資料側已手動處理（或不需處理）。</p>
            <Label className="mt-3 block text-xs">原因（必填，會寫入 audit log）</Label>
            <Input
              autoFocus
              value={abandonReason}
              onChange={(e) => setAbandonReason(e.target.value)}
              placeholder="例：upstream 已手動清，無需 sync"
              className="mt-1"
            />
          </>
        }
        confirmLabel="永久放棄"
        isPending={abandon.isPending}
        onConfirm={() => {
          if (!pendingAbandonId || !abandonReason.trim()) return;
          abandon.mutate(
            { eventId: pendingAbandonId, reason: abandonReason.trim() },
            {
              onSettled: () => {
                setPendingAbandonId(null);
                setAbandonReason("");
              },
            },
          );
        }}
      />
    </div>
  );
}

type StatCardProps = {
  label: string;
  value: number | string | undefined;
  tone: "muted" | "warning" | "danger";
};

function StatCard({ label, value, tone }: StatCardProps) {
  const toneClass =
    tone === "danger"
      ? "border-destructive/40 bg-destructive/5"
      : tone === "warning"
        ? "border-amber-500/40 bg-amber-500/5"
        : "border-border bg-muted/20";
  return (
    <div className={`rounded-md border px-4 py-3 ${toneClass}`}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">
        {value === undefined ? "…" : value}
      </div>
    </div>
  );
}

type DeadLetterTableProps = {
  events: OutboxEvent[];
  onRetry: (id: string) => void;
  onAbandon: (id: string) => void;
  retryingId: string | null;
};

function DeadLetterTable({
  events,
  onRetry,
  onAbandon,
  retryingId,
}: DeadLetterTableProps) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground bg-muted/30 border rounded-md px-3 py-6 text-center">
        🎉 DLQ 是空的
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left">
          <tr>
            <th className="px-3 py-2 font-medium">事件 ID</th>
            <th className="px-3 py-2 font-medium">類型</th>
            <th className="px-3 py-2 font-medium">Aggregate</th>
            <th className="px-3 py-2 font-medium">Tenant</th>
            <th className="px-3 py-2 font-medium">嘗試次數</th>
            <th className="px-3 py-2 font-medium">年齡</th>
            <th className="px-3 py-2 font-medium">最後錯誤</th>
            <th className="px-3 py-2 font-medium text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr
              key={e.id}
              className="border-t hover:bg-muted/30 transition-colors"
              data-testid={`dlq-row-${e.id}`}
            >
              <td className="px-3 py-2 font-mono text-xs">
                {e.id.slice(0, 8)}…
              </td>
              <td className="px-3 py-2 font-mono text-xs">{e.event_type}</td>
              <td className="px-3 py-2 font-mono text-xs">
                {e.aggregate_type}/{e.aggregate_id.slice(0, 12)}
              </td>
              <td className="px-3 py-2 font-mono text-xs">
                {e.tenant_id.slice(0, 8)}
              </td>
              <td className="px-3 py-2 tabular-nums">
                {e.attempts}/{e.max_attempts}
              </td>
              <td className="px-3 py-2 tabular-nums">
                {formatAge(e.age_seconds)}
              </td>
              <td className="px-3 py-2 max-w-xs truncate" title={e.last_error ?? ""}>
                {e.last_error ?? "—"}
              </td>
              <td className="px-3 py-2 text-right space-x-1">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={retryingId === e.id}
                  onClick={() => onRetry(e.id)}
                >
                  {retryingId === e.id ? "重排中…" : "重排"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  onClick={() => onAbandon(e.id)}
                >
                  放棄
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
