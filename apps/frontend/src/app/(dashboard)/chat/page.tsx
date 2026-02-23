"use client";

import { MessageList } from "@/features/chat/components/message-list";
import { ChatInput } from "@/features/chat/components/chat-input";

export default function ChatPage() {
  return (
    <div className="flex h-full flex-col">
      <MessageList />
      <ChatInput />
    </div>
  );
}
