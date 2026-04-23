import { useMemo, useState } from "react";
import { useAgentTraces } from "@/hooks/queries/use-agent-traces";
import { useAgentTraceDetail } from "@/hooks/queries/use-agent-traces";
import { AgentTraceDetail } from "@/features/admin/components/agent-trace-detail";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface Props {
  conversationId: string;
}

export function ConversationTraceTab({ conversationId }: Props) {
  const filters = useMemo(
    () => ({
      conversation_id: conversationId,
      limit: 50,
      offset: 0,
    }),
    [conversationId],
  );

  const { data, isLoading, error } = useAgentTraces(filters);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const detailQuery = useAgentTraceDetail(selectedTraceId);

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (error) {
    return (
      <p className="text-destructive text-sm">
        載入失敗：{(error as Error).message}
      </p>
    );
  }

  const traces = data?.items ?? [];

  if (traces.length === 0) {
    return (
      <p className="text-muted-foreground py-8 text-center">
        此對話沒有 agent trace 紀錄
      </p>
    );
  }

  if (selectedTraceId && detailQuery.data) {
    return (
      <div className="space-y-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSelectedTraceId(null)}
        >
          ← 返回 trace 列表
        </Button>
        <AgentTraceDetail
          trace={detailQuery.data}
          onBack={() => setSelectedTraceId(null)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        此對話共 {traces.length} 筆 trace（按時間降序）
      </p>
      {traces.map((t) => (
        <button
          key={t.trace_id}
          onClick={() => setSelectedTraceId(t.trace_id)}
          className="w-full text-left rounded-md border p-3 hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="font-mono">
              {t.trace_id.slice(0, 12)} · {t.agent_mode}
            </span>
            <span>
              {t.created_at
                ? new Date(t.created_at).toLocaleString("zh-TW")
                : ""}
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="font-medium">{t.llm_model}</span>
            <span className="text-muted-foreground">
              {t.total_ms}ms · {t.total_tokens?.total ?? 0} tokens
            </span>
            {t.outcome && (
              <span
                className={
                  t.outcome === "success"
                    ? "text-emerald-600"
                    : t.outcome === "failed"
                      ? "text-destructive"
                      : "text-amber-600"
                }
              >
                {t.outcome}
              </span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
