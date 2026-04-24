import { Link } from "react-router-dom";
import { Pencil } from "lucide-react";
import { useConversationMessages } from "@/hooks/queries/use-conversation-insights";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface RetrievedChunkDict {
  chunk_id?: string;
  kb_id?: string;
  document_name?: string;
  content_snippet?: string;
  score?: number;
}

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
          {/* QualityEdit.1 P1: 引用 chunks 展開 + 跳轉 */}
          {m.retrieved_chunks &&
            Array.isArray(m.retrieved_chunks) &&
            m.retrieved_chunks.length > 0 && (
              <details className="text-xs">
                <summary className="cursor-pointer text-muted-foreground">
                  📚 引用 chunks ({m.retrieved_chunks.length})
                </summary>
                <div className="mt-2 space-y-2">
                  {(m.retrieved_chunks as RetrievedChunkDict[]).map((c, i) => {
                    const canJump = !!(c.chunk_id && c.kb_id);
                    return (
                      <div
                        key={i}
                        className="rounded border bg-card p-2 space-y-1"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 text-muted-foreground text-[10px]">
                            <span className="font-mono">[{i + 1}]</span>
                            {c.document_name && (
                              <span className="truncate max-w-[200px]">
                                📄 {c.document_name}
                              </span>
                            )}
                            {typeof c.score === "number" && (
                              <span className="font-mono">
                                {c.score.toFixed(3)}
                              </span>
                            )}
                          </div>
                          {canJump && (
                            <Link
                              to={`/admin/kb-studio/${c.kb_id}?tab=chunks&highlight=${c.chunk_id}`}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] hover:bg-muted transition-colors"
                              title="到 KB Studio 編輯此 chunk"
                            >
                              <Pencil className="h-2.5 w-2.5" />
                              修正
                            </Link>
                          )}
                        </div>
                        {c.content_snippet && (
                          <p className="text-xs whitespace-pre-wrap line-clamp-3">
                            {c.content_snippet}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
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
