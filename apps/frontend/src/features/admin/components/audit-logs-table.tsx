/** Issue #60 — 稽核紀錄表格：變更欄位可展開看 before/after */

import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/format-date";
import type { AuditLog } from "@/types/audit-log";
import { ConfigDiffTable } from "./config-diff-table";

export const ENTITY_TYPE_LABEL: Record<string, string> = {
  guard_rules: "安全規則",
  system_prompt: "系統提示詞",
  bot: "機器人",
  worker: "Worker",
  tenant: "租戶",
};

export const ACTION_LABEL: Record<string, string> = {
  create: "建立",
  update: "更新",
  delete: "刪除",
  reset: "重設",
};

function actionBadgeClass(action: string): string {
  switch (action) {
    case "create":
      return "border-green-600/50 text-green-700 dark:text-green-400";
    case "delete":
      return "border-destructive/60 text-destructive";
    case "reset":
      return "border-amber-500/60 text-amber-600 dark:text-amber-400";
    default:
      return "";
  }
}

function shortId(id: string | null): string {
  if (!id) return "—";
  return id.length > 12 ? `${id.slice(0, 12)}…` : id;
}

interface AuditLogsTableProps {
  items: AuditLog[];
  /** tenant_id → 名稱（可選；沒有時顯示縮短 id） */
  tenantNames?: Record<string, string>;
}

export function AuditLogsTable({ items, tenantNames }: AuditLogsTableProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground" data-testid="audit-empty">
        沒有符合條件的稽核紀錄
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>時間</TableHead>
            <TableHead>租戶</TableHead>
            <TableHead>操作者</TableHead>
            <TableHead>類型</TableHead>
            <TableHead>對象</TableHead>
            <TableHead>動作</TableHead>
            <TableHead>變更欄位</TableHead>
            <TableHead>來源</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((log) => {
            const fieldCount = Object.keys(log.changed_fields ?? {}).length;
            const isOpen = !!expanded[log.id];
            return (
              <Fragment key={log.id}>
                <TableRow data-testid={`audit-row-${log.id}`}>
                  <TableCell className="whitespace-nowrap text-sm">
                    {formatDateTime(log.created_at)}
                  </TableCell>
                  <TableCell className="text-sm" title={log.tenant_id ?? undefined}>
                    {log.tenant_id
                      ? (tenantNames?.[log.tenant_id] ?? shortId(log.tenant_id))
                      : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs" title={log.actor_user_id ?? undefined}>
                    {shortId(log.actor_user_id)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-xs">
                      {ENTITY_TYPE_LABEL[log.entity_type] ?? log.entity_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs" title={log.entity_id ?? undefined}>
                    {shortId(log.entity_id)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`text-xs ${actionBadgeClass(log.action)}`}>
                      {ACTION_LABEL[log.action] ?? log.action}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {fieldCount > 0 ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        aria-expanded={isOpen}
                        onClick={() =>
                          setExpanded((prev) => ({ ...prev, [log.id]: !isOpen }))
                        }
                      >
                        {isOpen ? (
                          <ChevronDown className="mr-1 h-3 w-3" />
                        ) : (
                          <ChevronRight className="mr-1 h-3 w-3" />
                        )}
                        {fieldCount} 個欄位
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {log.source ?? "—"}
                  </TableCell>
                </TableRow>
                {isOpen && (
                  <TableRow data-testid={`audit-detail-${log.id}`}>
                    <TableCell colSpan={8} className="bg-muted/30">
                      <ConfigDiffTable changedFields={log.changed_fields} emptyText="無欄位變更" />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
