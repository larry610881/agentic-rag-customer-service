import { Loader2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCompileWiki, useWikiStatus } from "@/hooks/queries/use-wiki";
import { cn } from "@/lib/utils";
import type { WikiStatus } from "@/types/bot";

type CompileWikiCardProps = {
  botId: string;
};

const STATUS_LABELS: Record<WikiStatus, string> = {
  pending: "尚未編譯",
  compiling: "編譯中",
  ready: "已就緒",
  stale: "需重新編譯",
  failed: "編譯失敗",
};

const STATUS_BADGE_CLASS: Record<WikiStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  compiling: "bg-blue-500 text-white",
  ready: "bg-green-600 text-white",
  stale: "bg-yellow-500 text-white",
  failed: "bg-destructive text-white",
};

export const CompileWikiCard = ({ botId }: CompileWikiCardProps) => {
  const statusQuery = useWikiStatus(botId, "wiki");
  const compileMutation = useCompileWiki();

  const handleCompile = () => {
    compileMutation.mutate(botId);
  };

  const status = statusQuery.data?.status;
  const isPolling = status === "compiling";
  const isCompileDisabled = compileMutation.isPending || isPolling;

  return (
    <Card data-testid="compile-wiki-card">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="text-base">Wiki 編譯狀態</CardTitle>
        <WikiStatusBadge
          status={status}
          isLoading={statusQuery.isLoading}
          hasError={statusQuery.isError}
        />
      </CardHeader>
      <CardContent className="space-y-4">
        {statusQuery.isLoading && (
          <p className="text-sm text-muted-foreground">載入狀態中…</p>
        )}

        {statusQuery.isError && (
          <p className="text-sm text-muted-foreground">
            尚未編譯過 Wiki，按下方按鈕開始編譯。
          </p>
        )}

        {statusQuery.data && (
          <WikiStats data={statusQuery.data} />
        )}

        {status === "stale" && (
          <p className="text-sm text-yellow-600 dark:text-yellow-400">
            ⚠️ 知識庫文件已更新，建議重新編譯以取得最新內容。
          </p>
        )}

        {status === "failed" && statusQuery.data?.errors && (
          <ErrorList errors={statusQuery.data.errors} />
        )}

        <CompileButton
          disabled={isCompileDisabled}
          isPending={compileMutation.isPending}
          onConfirm={handleCompile}
        />
      </CardContent>
    </Card>
  );
};

type WikiStatusBadgeProps = {
  status: WikiStatus | undefined;
  isLoading: boolean;
  hasError: boolean;
};

const WikiStatusBadge = ({
  status,
  isLoading,
  hasError,
}: WikiStatusBadgeProps) => {
  if (isLoading) {
    return <Badge variant="outline">載入中</Badge>;
  }
  if (hasError || !status) {
    return <Badge variant="outline">未編譯</Badge>;
  }

  const label = STATUS_LABELS[status];
  const badgeClass = STATUS_BADGE_CLASS[status];

  return (
    <Badge data-testid="wiki-status-badge" className={cn(badgeClass)}>
      {status === "compiling" && (
        <Loader2 className="size-3 animate-spin" aria-hidden="true" />
      )}
      {label}
    </Badge>
  );
};

type WikiStatsProps = {
  data: NonNullable<ReturnType<typeof useWikiStatus>["data"]>;
};

const WikiStats = ({ data }: WikiStatsProps) => {
  return (
    <div className="space-y-2 rounded-md bg-muted/50 p-3 text-sm">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="文件" value={data.doc_count} />
        <Stat label="節點" value={data.node_count} />
        <Stat label="關係" value={data.edge_count} />
        <Stat label="群組" value={data.cluster_count} />
      </div>
      {data.token_usage && (
        <div className="border-t border-border pt-2">
          <p className="text-xs text-muted-foreground">
            Token 使用：input {data.token_usage.input.toLocaleString()} /
            output {data.token_usage.output.toLocaleString()} ／
            預估成本 ${data.token_usage.estimated_cost.toFixed(4)} USD
          </p>
        </div>
      )}
      {data.compiled_at && (
        <p className="text-xs text-muted-foreground">
          上次編譯：{new Date(data.compiled_at).toLocaleString()}
        </p>
      )}
    </div>
  );
};

const Stat = ({ label, value }: { label: string; value: number }) => (
  <div>
    <p className="text-xs text-muted-foreground">{label}</p>
    <p className="font-mono text-base">{value}</p>
  </div>
);

type ErrorListProps = {
  errors: string[];
};

const ErrorList = ({ errors }: ErrorListProps) => {
  if (errors.length === 0) return null;
  return (
    <div className="space-y-1 rounded-md border border-destructive/50 bg-destructive/10 p-3">
      <p className="text-sm font-medium text-destructive">編譯錯誤：</p>
      <ul className="list-inside list-disc space-y-0.5 text-xs text-destructive">
        {errors.slice(0, 5).map((err, idx) => (
          <li key={idx}>{err}</li>
        ))}
        {errors.length > 5 && (
          <li className="italic">…還有 {errors.length - 5} 個錯誤</li>
        )}
      </ul>
    </div>
  );
};

type CompileButtonProps = {
  disabled: boolean;
  isPending: boolean;
  onConfirm: () => void;
};

const CompileButton = ({
  disabled,
  isPending,
  onConfirm,
}: CompileButtonProps) => {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          type="button"
          disabled={disabled}
          data-testid="compile-wiki-button"
        >
          {isPending ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" />
              觸發中…
            </>
          ) : (
            "編譯 Wiki"
          )}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>確認編譯 Wiki？</AlertDialogTitle>
          <AlertDialogDescription>
            編譯會呼叫 LLM 處理知識庫的所有文件，會消耗 token 並產生費用。
            編譯時間視文件數量約需數秒到數分鐘。確定要繼續嗎？
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            data-testid="compile-wiki-confirm"
          >
            確認編譯
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
