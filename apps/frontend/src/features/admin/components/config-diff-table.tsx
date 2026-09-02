/** Issue #60 — 兩份快照的差異表：欄位 | 變更前 | 變更後（長字串預設收合） */

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ConfigFieldChange } from "@/types/config-snapshot";

export const COLLAPSE_THRESHOLD = 120;

export function formatDiffValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function CollapsibleValue({
  value,
  testId,
}: {
  value: unknown;
  testId?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const text = formatDiffValue(value);
  const isLong = text.length > COLLAPSE_THRESHOLD;
  const shown = isLong && !expanded ? `${text.slice(0, COLLAPSE_THRESHOLD)}…` : text;

  return (
    <div className="space-y-1" data-testid={testId}>
      <pre className="whitespace-pre-wrap break-all font-mono text-xs">
        {shown}
      </pre>
      {isLong && (
        <Button
          type="button"
          variant="link"
          size="sm"
          className="h-auto p-0 text-xs"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "收合" : "展開"}
        </Button>
      )}
    </div>
  );
}

interface ConfigDiffTableProps {
  changedFields: Record<string, ConfigFieldChange>;
  /** 無差異時顯示的文字 */
  emptyText?: string;
}

export function ConfigDiffTable({
  changedFields,
  emptyText = "兩份設定完全相同",
}: ConfigDiffTableProps) {
  const entries = Object.entries(changedFields).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="config-diff-empty">
        {emptyText}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border" data-testid="config-diff-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[220px]">欄位</TableHead>
            <TableHead>變更前</TableHead>
            <TableHead>變更後</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([field, change]) => (
            <TableRow key={field} data-testid={`config-diff-row-${field}`}>
              <TableCell className="align-top font-mono text-xs">{field}</TableCell>
              <TableCell className="align-top">
                <CollapsibleValue value={change.before} />
              </TableCell>
              <TableCell className="align-top">
                <CollapsibleValue value={change.after} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
