"use client";

import { AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/use-chat-store";
import type { ChatMessage } from "@/types/chat";
import { ToolHintIndicator } from "@/features/chat/components/tool-hint-indicator";
import { FeedbackButtons } from "@/features/chat/components/feedback-buttons";

interface MessageBubbleProps {
  message: ChatMessage;
  isLast?: boolean;
}

export function MessageBubble({ message, isLast }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const toolHint = useChatStore((s) => s.toolHint);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const conversationId = useChatStore((s) => s.conversationId);

  const showHint = !isUser && isLast && isStreaming && !!toolHint && !message.content;
  const showFeedback = !isUser && message.content && !(isLast && isStreaming);

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-2",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground",
        )}
      >
        <AnimatePresence mode="wait">
          {showHint ? (
            <ToolHintIndicator key="hint" hint={toolHint} />
          ) : (
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          )}
        </AnimatePresence>
        {showFeedback && conversationId && (
          <FeedbackButtons
            messageId={message.id}
            conversationId={conversationId}
            feedbackRating={message.feedbackRating}
          />
        )}
      </div>
    </div>
  );
}
