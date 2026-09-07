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
import { useBotAuditLogs } from "@/hooks/queries/use-bot-audit-logs";
import { formatDateTime } from "@/lib/format-date";
import { isLongTextChange, type BotAuditChange, type BotAuditLogEntry } from "@/types/bot-audit-log";

export const BOT_AUDIT_ACTION_LABEL: Record<string, string> = {
  create: "建立",
  update: "更新",
  delete: "刪除",
  reset: "重設",
};

function actorLabel(entry: BotAuditLogEntry): string {
  if (entry.actor_email) return entry.actor_email;
  if (entry.actor_user_id) return `${entry.actor_user_id.slice(0, 8)}…`;
  return "系統";
}

function ChangeRow({ change }: { change: BotAuditChange }) {
  const label = botFieldLabel(change.field);
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
        {formatBotFieldValue(change.field, change.before)}
      </span>
      <span aria-hidden="true">→</span>
      <span className="break-all font-mono text-xs">
        {formatBotFieldValue(change.field, change.after)}
      </span>
    </li>
  );
}

function EntryRow({ entry }: { entry: BotAuditLogEntry }) {
  const [open, setOpen] = useState(false);
  const count = entry.changes.length;
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
            <ChangeRow key={c.field} change={c} />
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
