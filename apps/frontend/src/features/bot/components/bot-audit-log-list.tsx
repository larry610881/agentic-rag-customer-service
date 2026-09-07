/** Issue #71 — bot 詳情「變更紀錄」：誰在何時改了哪些欄位，可展開看前後值 */

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  botFieldLabel,
  describeLengthChange,
  formatBotFieldValue,
} from "@/features/bot/bot-field-labels";
import {
  formatWorkerFieldValue,
  workerFieldLabel,
} from "@/features/bot/worker-field-labels";
import { useBotAuditLogs } from "@/hooks/queries/use-bot-audit-logs";
import { formatDateTime } from "@/lib/format-date";
import { isLongTextChange, type BotAuditChange, type BotAuditLogEntry } from "@/types/bot-audit-log";

export const BOT_AUDIT_ACTION_LABEL: Record<string, string> = {
  create: "建立",
  update: "更新",
  delete: "刪除",
  reset: "重設",
};

/**
 * Issue #75 / #77 — 非 bot 本體的變更以實體標籤區分：
 * 平台改了租戶的防護設定 → 「防護設定（平台）」；worker → 「worker：<名稱>」。
 * bot 本體不顯示標籤（entity_type 缺省時視為 bot，相容舊資料）。
 */
export function entityBadgeLabel(entry: BotAuditLogEntry): string | null {
  switch (entry.entity_type) {
    case "guard_settings":
      return "防護設定（平台）";
    case "worker":
      return entry.entity_name ? `worker：${entry.entity_name}` : "worker";
    default:
      return null;
  }
}

/** worker 列用 worker 欄位對照表，其餘沿用 bot 對照表 */
function fieldFormatters(entry: BotAuditLogEntry) {
  if (entry.entity_type === "worker") {
    return { label: workerFieldLabel, format: formatWorkerFieldValue };
  }
  return { label: botFieldLabel, format: formatBotFieldValue };
}

function actorLabel(entry: BotAuditLogEntry): string {
  if (entry.actor_label) return entry.actor_label;
  if (entry.actor_email) return entry.actor_email;
  if (entry.actor_user_id) return `${entry.actor_user_id.slice(0, 8)}…`;
  return "系統";
}

function ChangeRow({
  change,
  entry,
}: {
  change: BotAuditChange;
  entry: BotAuditLogEntry;
}) {
  const { label: labelOf, format } = fieldFormatters(entry);
  const label = labelOf(change.field);
  if (isLongTextChange(change)) {
    return (
      <li className="flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">
          {describeLengthChange(change.before_len, change.after_len)}
        </span>
      </li>
    );
  }
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 text-sm">
      <span className="font-medium">{label}</span>
      <span className="break-all font-mono text-xs text-muted-foreground line-through">
        {format(change.field, change.before)}
      </span>
      <span aria-hidden="true">→</span>
      <span className="break-all font-mono text-xs">
        {format(change.field, change.after)}
      </span>
    </li>
  );
}

function EntryRow({ entry }: { entry: BotAuditLogEntry }) {
  const [open, setOpen] = useState(false);
  const count = entry.changes.length;
  const entityBadge = entityBadgeLabel(entry);
  return (
    <li className="rounded-md border p-3" data-testid={`bot-audit-row-${entry.id}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="whitespace-nowrap text-muted-foreground">
          {formatDateTime(entry.created_at)}
        </span>
        <span className="font-medium" title={entry.actor_user_id ?? undefined}>
          {actorLabel(entry)}
        </span>
        <Badge variant="outline" className="text-xs">
          {BOT_AUDIT_ACTION_LABEL[entry.action] ?? entry.action}
        </Badge>
        {entityBadge && (
          <Badge variant="secondary" className="text-xs">
            {entityBadge}
          </Badge>
        )}
        {count > 0 ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? (
              <ChevronDown className="mr-1 h-3 w-3" />
            ) : (
              <ChevronRight className="mr-1 h-3 w-3" />
            )}
            {count} 個欄位
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">無欄位變更</span>
        )}
      </div>
      {open && (
        <ul
          className="mt-2 space-y-1 border-t pt-2"
          data-testid={`bot-audit-detail-${entry.id}`}
        >
          {entry.changes.map((c) => (
            <ChangeRow key={c.field} change={c} entry={entry} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function BotAuditLogList({ botId }: { botId: string }) {
  const { data, isLoading, isError, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useBotAuditLogs(botId);

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="bot-audit-loading">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }
  if (isError) {
    return <p className="text-sm text-destructive">載入變更紀錄失敗。</p>;
  }

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="bot-audit-empty">
        尚無變更紀錄
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {items.map((entry) => (
          <EntryRow key={entry.id} entry={entry} />
        ))}
      </ul>
      {hasNextPage && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isFetchingNextPage}
          onClick={() => void fetchNextPage()}
        >
          {isFetchingNextPage ? "載入中..." : "載入更多"}
        </Button>
      )}
    </div>
  );
}
