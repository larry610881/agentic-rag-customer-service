import { useConversationMessages } from "@/hooks/queries/use-conversation-insights";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { ConversationMessagesTab } from "./conversation-messages-tab";
import { ConversationTraceTab } from "./conversation-trace-tab";
import { ConversationSummaryTab } from "./conversation-summary-tab";
import { ConversationTokenUsageTab } from "./conversation-token-usage-tab";

interface Props {
  conversationId: string;
  tab: string;
  onTabChange: (tab: string) => void;
  // summary 從 left list item 傳進來（已預先拿到）
  summaryFromList: string | null | undefined;
}

export function ConversationDetailPanel({
  conversationId,
  tab,
  onTabChange,
  summaryFromList,
}: Props) {
  // Fetch metadata once (shared by 訊息 + 摘要 tab)
  const { data: metadata } = useConversationMessages(conversationId);

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="font-mono">
          {conversationId.slice(0, 12)}...
          <button
            onClick={() => navigator.clipboard?.writeText(conversationId)}
            className="ml-2 text-primary hover:underline"
            title="複製 conversation_id"
          >
            複製
          </button>
        </span>
        {metadata && (
          <>
            <span>租戶 {metadata.tenant_id.slice(0, 8)}</span>
            {metadata.bot_id && <span>Bot {metadata.bot_id.slice(0, 8)}</span>}
            <span>{metadata.message_count} 則訊息</span>
          </>
        )}
      </div>

      <Tabs value={tab} onValueChange={onTabChange}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="messages">訊息</TabsTrigger>
          <TabsTrigger value="trace">Agent Trace</TabsTrigger>
          <TabsTrigger value="summary">摘要</TabsTrigger>
          <TabsTrigger value="token">Token 用量</TabsTrigger>
        </TabsList>

        <TabsContent value="messages" className="mt-4">
          <ConversationMessagesTab conversationId={conversationId} />
        </TabsContent>
        <TabsContent value="trace" className="mt-4">
          <ConversationTraceTab conversationId={conversationId} />
        </TabsContent>
        <TabsContent value="summary" className="mt-4">
          <ConversationSummaryTab
            summary={metadata?.summary ?? summaryFromList}
            lastMessageAt={metadata?.last_message_at}
            messageCount={metadata?.message_count ?? 0}
          />
        </TabsContent>
        <TabsContent value="token" className="mt-4">
          <ConversationTokenUsageTab conversationId={conversationId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
