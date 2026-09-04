import { useEffect, useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
import type { AbuseControlItem } from "@/types/abuse-control";
import {
  controlKey,
  formatRemaining,
  levelLabel,
  subjectKindLabel,
} from "@/features/abuse-control/abuse-setting-labels";

interface AbuseControlsTableProps {
  items: AbuseControlItem[] | undefined;
  isLoading?: boolean;
  /** 資料取得時間（ms）；提供時剩餘時間會在本地倒數 */
  fetchedAt?: number;
  tenantNameOf?: (tenantId: string) => string | undefined;
  /** 提供時顯示「解除」欄；tenant_admin 唯讀頁不傳 */
  onRelease?: (item: AbuseControlItem) => void;
  isReleasing?: boolean;
}

function levelVariant(level: number): "outline" | "secondary" | "default" | "destructive" {
  if (level >= 4) return "destructive";
  if (level === 3) return "default";
  if (level === 2) return "secondary";
  return "outline";
}

export function LevelBadge({ level }: { level: number }) {
  return (
    <Badge variant={levelVariant(level)}>
      L{level} {levelLabel(level)}
    </Badge>
  );
}

export function AbuseControlsTable({
  items,
  isLoading = false,
  fetchedAt,
  tenantNameOf,
  onRelease,
  isReleasing = false,
}: AbuseControlsTableProps) {
  const [now, setNow] = useState(() => Date.now());
  const [pending, setPending] = useState<AbuseControlItem | null>(null);

  const hasItems = !!items && items.length > 0;
  useEffect(() => {
    if (!hasItems || fetchedAt === undefined) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [hasItems, fetchedAt]);

  const remainingOf = (item: AbuseControlItem) =>
    fetchedAt === undefined
      ? item.remaining_seconds
      : item.remaining_seconds - (now - fetchedAt) / 1000;

  if (isLoading && !items) {
    return <p className="text-muted-foreground">載入中…</p>;
  }
  if (!hasItems) {
    return <p className="text-muted-foreground">目前沒有受控中的主體</p>;
  }

  return (
    <>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>租戶</TableHead>
              <TableHead>主體類型</TableHead>
              <TableHead>主體</TableHead>
              <TableHead>等級</TableHead>
              <TableHead>剩餘時間</TableHead>
              {onRelease && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items!.map((item) => (
              <TableRow key={controlKey(item)}>
                <TableCell>
                  <div className="font-medium">
                    {tenantNameOf?.(item.tenant_id) ?? item.tenant_id}
                  </div>
                  {tenantNameOf?.(item.tenant_id) && (
                    <div className="font-mono text-xs text-muted-foreground">
                      {item.tenant_id}
                    </div>
                  )}
                </TableCell>
                <TableCell>{subjectKindLabel(item.subject_kind)}</TableCell>
                <TableCell className="font-mono text-sm">{item.subject_masked}</TableCell>
                <TableCell>
                  <LevelBadge level={item.level} />
                </TableCell>
                <TableCell className="font-mono tabular-nums">
                  {formatRemaining(remainingOf(item))}
                </TableCell>
                {onRelease && (
                  <TableCell>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={isReleasing || !item.subject_id}
                      onClick={() => setPending(item)}
                    >
                      解除
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {onRelease && (
        <AlertDialog open={!!pending} onOpenChange={(open) => !open && setPending(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>確認解除控管？</AlertDialogTitle>
              <AlertDialogDescription>
                {pending
                  ? `將解除 ${subjectKindLabel(pending.subject_kind)} ${pending.subject_masked} 的 L${pending.level} ${levelLabel(pending.level)}，分數歸零並寫入稽核紀錄。`
                  : ""}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault();
                  if (pending) onRelease(pending);
                  setPending(null);
                }}
              >
                確認解除
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </>
  );
}
