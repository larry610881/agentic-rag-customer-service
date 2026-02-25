"use client";

import { useEffect, useState } from "react";
import { ArrowLeftRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useConversations, useConversation } from "@/hooks/queries/use-conversations";
import { useChatStore } from "@/stores/use-chat-store";
import { ConversationItem } from "./conversation-item";

export function ConversationList() {
  const { data: conversations } = useConversations();
  const conversationId = useChatStore((s) => s.conversationId);
  const botName = useChatStore((s) => s.botName);
  const clearBot = useChatStore((s) => s.clearBot);
  const clearMessages = useChatStore((s) => s.clearMessages);
  const loadConversation = useChatStore((s) => s.loadConversation);

  // Track which conversation we're loading (to fetch its detail)
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const { data: detail } = useConversation(loadingId);

  // Load conversation detail into store when it arrives
  useEffect(() => {
    if (detail && detail.id === loadingId) {
      loadConversation(detail);
      setLoadingId(null);
    }
  }, [detail, loadingId, loadConversation]);

  const handleSelect = (id: string) => {
    if (id === conversationId) return;
    setLoadingId(id);
  };

  const handleNew = () => {
    setLoadingId(null);
    clearMessages();
  };

  return (
    <div className="flex h-full flex-col border-r">
      {botName && (
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="truncate text-sm font-medium">{botName}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearBot}
            className="h-7 shrink-0 gap-1 px-2 text-xs"
          >
            <ArrowLeftRight className="h-3 w-3" />
            切換
          </Button>
        </div>
      )}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <h2 className="text-sm font-semibold">Conversations</h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleNew}
          aria-label="New conversation"
          className="h-7 w-7"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex flex-col gap-1 p-2">
          {conversations && conversations.length > 0 ? (
            conversations.map((c) => (
              <ConversationItem
                key={c.id}
                conversation={c}
                isActive={c.id === conversationId}
                onClick={() => handleSelect(c.id)}
              />
            ))
          ) : (
            <p className="px-3 py-4 text-center text-xs text-muted-foreground">
              No conversations yet
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
