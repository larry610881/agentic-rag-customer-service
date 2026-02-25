"use client";

import { useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useChatStore } from "@/stores/use-chat-store";
import { useStreaming } from "@/features/chat/hooks/use-streaming";

export function ChatInput() {
  const [input, setInput] = useState("");
  const isStreaming = useChatStore((s) => s.isStreaming);
  const botId = useChatStore((s) => s.botId);
  const { sendMessage } = useStreaming();

  const canSend = !!input.trim() && !isStreaming && !!botId;

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || !botId) return;
    setInput("");
    sendMessage(trimmed);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex gap-2 border-t bg-background p-4">
      <Textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="輸入訊息..."
        className="min-h-[40px] resize-none"
        rows={1}
        disabled={isStreaming}
        aria-label="訊息輸入"
      />
      <Button onClick={handleSend} disabled={!canSend}>
        {isStreaming ? "傳送中..." : "傳送"}
      </Button>
    </div>
  );
}
