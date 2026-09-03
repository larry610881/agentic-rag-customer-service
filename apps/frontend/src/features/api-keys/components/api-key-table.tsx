/** Issue #67 P2 — API 金鑰列表 */
import { useState } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import { formatDateTime } from "@/lib/format-date";
import { useApiKeys, useRevokeApiKey } from "@/hooks/queries/use-api-keys";
import {
  API_KEY_SCOPE_LABELS,
  API_KEY_STATUS_LABELS,
  getApiKeyStatus,
  type ApiKey,
  type ApiKeyStatus,
} from "@/types/api-key";

const STATUS_VARIANT: Record<ApiKeyStatus, "default" | "destructive" | "outline"> = {
  active: "default",
  revoked: "destructive",
  expired: "outline",
};

interface ApiKeyTableProps {
  /** system_admin 用來過濾租戶；tenant_admin 不需傳 */
  tenantId?: string;
}

export function ApiKeyTable({ tenantId }: ApiKeyTableProps) {
  const { data, isLoading, isError } = useApiKeys(tenantId);
  const revokeMutation = useRevokeApiKey();
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null);

  const handleRevoke = () => {
    if (!revokeTarget) return;
    revokeMutation.mutate(revokeTarget.id, {
      onSuccess: () => {
        toast.success(`已撤銷金鑰「${revokeTarget.name}」`);
        setRevokeTarget(null);
      },
      onError: () => toast.error("撤銷失敗，請稍後再試"),
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="api-key-table-loading">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <p className="text-sm text-destructive">載入 API 金鑰失敗，請重新整理。</p>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
        尚未建立任何 API 金鑰。
      </div>
    );
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名稱</TableHead>
              <TableHead>金鑰前綴</TableHead>
              <TableHead>權限範圍</TableHead>
              <TableHead>允許機器人</TableHead>
              <TableHead>狀態</TableHead>
              <TableHead>最後使用</TableHead>
              <TableHead>建立時間</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((key) => {
              const status = getApiKeyStatus(key);
              return (
                <TableRow key={key.id}>
                  <TableCell>
                    <div className="font-medium">{key.name}</div>
                    {key.description && (
                      <div className="text-xs text-muted-foreground">
                        {key.description}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {key.secret_prefix}…
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {key.scopes.map((scope) => (
                        <Badge
                          key={scope}
                          variant="secondary"
                          title={API_KEY_SCOPE_LABELS[scope] ?? scope}
                        >
                          {scope}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    {key.allowed_bot_ids.length === 0
                      ? "全部"
                      : `${key.allowed_bot_ids.length} 個`}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[status]}>
                      {API_KEY_STATUS_LABELS[status]}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {key.last_used_at ? formatDateTime(key.last_used_at) : "從未使用"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(key.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    {status === "active" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setRevokeTarget(key)}
                      >
                        撤銷
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <ConfirmDangerDialog
        open={!!revokeTarget}
        onOpenChange={(open) => {
          if (!open) setRevokeTarget(null);
        }}
        title="撤銷 API 金鑰"
        description={`撤銷後，使用「${revokeTarget?.name ?? ""}」取得的 access token 將立即失效，且無法復原。`}
        confirmLabel="確認撤銷"
        isPending={revokeMutation.isPending}
        onConfirm={handleRevoke}
      />
    </>
  );
}
