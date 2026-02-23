"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useChatStore } from "@/stores/use-chat-store";
import { MessageBubble } from "@/features/chat/components/message-bubble";
import { CitationList } from "@/features/chat/components/citation-list";
import { AgentThoughtPanel } from "@/features/chat/components/agent-thought-panel";

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Start a conversation by sending a message.</p>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 p-4">
      <div className="flex flex-col gap-4">
        {messages.map((message) => (
          <div key={message.id} className="flex flex-col gap-2">
            <MessageBubble message={message} />
            {message.role === "assistant" && message.tool_calls && message.tool_calls.length > 0 && (
              <AgentThoughtPanel toolCalls={message.tool_calls} />
            )}
            {message.role === "assistant" && message.sources && message.sources.length > 0 && (
              <CitationList sources={message.sources} />
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
