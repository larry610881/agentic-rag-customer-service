import { useConversationMessages } from "@/hooks/queries/use-conversation-insights";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface Props {
  conversationId: string;
}

export function ConversationMessagesTab({ conversationId }: Props) {
  const { data, isLoading, error } = useConversationMessages(conversationId);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-destructive text-sm">
        載入失敗：{(error as Error).message}
      </p>
    );
  }

  if (!data?.messages.length) {
    return (
      <p className="text-muted-foreground py-8 text-center">
        此對話沒有訊息
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {data.messages.map((m) => (
        <div
          key={m.message_id}
          className={cn(
            "flex flex-col gap-1 rounded-md border p-3",
            m.role === "assistant" && "bg-muted/30",
            m.role === "system" && "bg-amber-50 dark:bg-amber-950/20",
          )}
        >
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium">
              {m.role === "user"
                ? "👤 User"
                : m.role === "assistant"
                  ? "🤖 Assistant"
                  : `⚙️ ${m.role}`}
            </span>
            <span className="font-mono">
              {m.created_at
                ? new Date(m.created_at).toLocaleString("zh-TW")
                : "—"}
            </span>
          </div>
          <pre className="text-sm whitespace-pre-wrap break-words font-sans">
            {m.content}
          </pre>
          {m.tool_calls && m.tool_calls.length > 0 && (
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">
                Tool calls ({m.tool_calls.length})
              </summary>
              <pre className="mt-1 overflow-auto p-2 bg-muted/50 rounded">
                {JSON.stringify(m.tool_calls, null, 2)}
              </pre>
            </details>
          )}
          {m.latency_ms != null && (
            <span className="text-xs text-muted-foreground">
              延遲 {m.latency_ms}ms
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
