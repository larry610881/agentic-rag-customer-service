"use client";

import { MessageList } from "@/features/chat/components/message-list";
import { ChatInput } from "@/features/chat/components/chat-input";
import { ConversationList } from "@/features/chat/components/conversation-list";
import { BotSelector } from "@/features/chat/components/bot-selector";
import { useChatStore } from "@/stores/use-chat-store";

export default function ChatPage() {
  const botId = useChatStore((s) => s.botId);

  if (!botId) {
    return <BotSelector />;
  }

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
