"use client";

import { useEffect } from "react";
import { MessageList } from "@/features/chat/components/message-list";
import { ChatInput } from "@/features/chat/components/chat-input";
import { ConversationList } from "@/features/chat/components/conversation-list";
import { useKnowledgeBases } from "@/hooks/queries/use-knowledge-bases";
import { useChatStore } from "@/stores/use-chat-store";

export default function ChatPage() {
  const { data: kbs } = useKnowledgeBases();
  const knowledgeBaseId = useChatStore((s) => s.knowledgeBaseId);
  const setKnowledgeBaseId = useChatStore((s) => s.setKnowledgeBaseId);

  useEffect(() => {
    if (!knowledgeBaseId && kbs && kbs.length > 0) {
      setKnowledgeBaseId(kbs[0].id);
    }
  }, [knowledgeBaseId, kbs, setKnowledgeBaseId]);

  return (
    <div className="flex h-full">
      <div className="w-64 shrink-0">
        <ConversationList />
      </div>
      <div className="flex flex-1 flex-col">
        <MessageList />
        <ChatInput />
      </div>
    </div>
  );
}
