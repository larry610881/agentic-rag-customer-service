import { useState } from "react";
import { Search, Sparkles } from "lucide-react";
import { useConversationSearch } from "@/hooks/queries/use-conversation-search";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { AdminBotFilter } from "@/features/admin/components/admin-bot-filter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";

interface Props {
  selectedConversationId: string | null;
  onSelect: (conversationId: string, summary: string | null | undefined) => void;
}

export function ConversationListPanel({ selectedConversationId, onSelect }: Props) {
  const [mode, setMode] = useState<"keyword" | "semantic">("keyword");
  const [input, setInput] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [tenantId, setTenantId] = useState<string | undefined>();
  const [botId, setBotId] = useState<string | undefined>();

  const { data, isLoading, isError } = useConversationSearch({
    mode,
    query: submittedQuery,
    tenantId,
    botId,
    limit: 50,
    enabled: submittedQuery.length > 0,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittedQuery(input.trim());
  };

  const items = data ?? [];

  return (
    <div className="flex flex-col gap-3">
      <div className="space-y-3 rounded-md border p-3">
        <ToggleGroup
          type="single"
          value={mode}
          onValueChange={(v) => {
            if (v === "keyword" || v === "semantic") {
              setMode(v);
              if (input.trim()) setSubmittedQuery(input.trim());
            }
          }}
          className="w-fit border rounded-md"
        >
          <ToggleGroupItem value="keyword" className="px-3 text-sm">
            <Search className="mr-1.5 h-3.5 w-3.5" />
            關鍵字
          </ToggleGroupItem>
          <ToggleGroupItem value="semantic" className="px-3 text-sm">
            <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            意思
          </ToggleGroupItem>
        </ToggleGroup>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            type="text"
            placeholder={
              mode === "keyword"
                ? "例：退貨、訂單"
                : "例：客戶不滿意"
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <Button type="submit" size="sm" disabled={!input.trim()}>
            搜尋
          </Button>
        </form>

        <div className="flex gap-2 flex-wrap">
          <AdminTenantFilter
            value={tenantId}
            onChange={(v) => {
              setTenantId(v);
              setBotId(undefined);
            }}
          />
          <AdminBotFilter
            value={botId}
            onChange={setBotId}
            tenantId={tenantId}
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto space-y-2">
        {!submittedQuery ? (
          <p className="text-muted-foreground text-sm py-8 text-center">
            輸入關鍵字或一句話描述，按搜尋開始
          </p>
        ) : isError ? (
          <p className="text-destructive text-sm py-6 text-center">
            搜尋失敗，請稍後重試
          </p>
        ) : isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="text-muted-foreground text-sm py-6 text-center">
            查無對應對話
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground px-1">
              找到 {items.length} 筆
            </p>
            {items.map((item) => {
              const isSelected = item.conversation_id === selectedConversationId;
              return (
                <button
                  key={item.conversation_id}
                  onClick={() => onSelect(item.conversation_id, item.summary)}
                  className={cn(
                    "w-full text-left rounded-md border p-3 transition-colors",
                    isSelected
                      ? "bg-primary/5 border-primary"
                      : "hover:bg-muted/50",
                  )}
                >
                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                    <span>{item.tenant_name}</span>
                    {item.score !== null && (
                      <span className="font-mono text-emerald-600">
                        {item.score.toFixed(3)}
                      </span>
                    )}
                  </div>
                  <p className="text-sm line-clamp-2">{item.summary}</p>
                  <div className="flex items-center justify-between text-xs text-muted-foreground mt-1">
                    <span>{item.message_count} 則訊息</span>
                    <span>
                      {item.last_message_at
                        ? new Date(item.last_message_at).toLocaleDateString(
                            "zh-TW",
                          )
                        : "—"}
                    </span>
                  </div>
                </button>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
