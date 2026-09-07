import { AnimatePresence } from "framer-motion";
import { ShieldAlert, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/use-chat-store";
import type { ChatMessage } from "@/types/chat";
import { ToolHintIndicator } from "@/features/chat/components/tool-hint-indicator";
import { FeedbackButtons } from "@/features/chat/components/feedback-buttons";

interface MessageBubbleProps {
  message: ChatMessage;
  isLast?: boolean;
}

const GUARD_BANNER_TEXT: Record<"input" | "output", string> = {
  input: "此訊息命中輸入過濾規則，已被攔截（Studio only）",
  output: "AI 回覆命中輸出關鍵字，已被替換為安全回應（Studio only）",
};

export function MessageBubble({ message, isLast }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const toolHint = useChatStore((s) => s.toolHint);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const conversationId = useChatStore((s) => s.conversationId);

  const showHint = !isUser && isLast && isStreaming && !!toolHint && !message.content;
  // Issue #74：額度用盡通知 — 不是 AI 回覆，不給回饋按鈕
  const isQuotaExhausted = !isUser && !!message.quotaExhausted;
  const showFeedback =
    !isUser && message.content && !(isLast && isStreaming) && !isQuotaExhausted;
  // Sprint A++ Guard UX: 被攔截時樣式與 banner（僅 Studio 收得到此 flag）
  const isGuardBlocked = !isUser && !!message.guardBlocked;

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-2",
          isUser
            ? "bg-primary text-primary-foreground"
            : isGuardBlocked
              ? "bg-orange-50 text-foreground border border-orange-400 dark:bg-orange-950/30 dark:border-orange-700"
              : isQuotaExhausted
                ? "bg-amber-50 text-foreground border border-amber-400 dark:bg-amber-950/30 dark:border-amber-700"
                : "bg-muted/80 text-foreground border border-border",
        )}
      >
        {isQuotaExhausted && (
          <div
            role="status"
            className="mb-2 flex items-center gap-2 rounded-md bg-amber-100 px-2 py-1.5 text-xs font-medium text-amber-900 dark:bg-amber-900/40 dark:text-amber-200"
          >
            <Wallet className="h-3.5 w-3.5 shrink-0" />
            本月額度已用完，服務暫停
          </div>
        )}
        {isGuardBlocked && message.guardBlocked && (
          <div className="mb-2 flex items-start gap-2 rounded-md bg-orange-100 px-2 py-1.5 text-xs text-orange-900 dark:bg-orange-900/40 dark:text-orange-200">
            <ShieldAlert className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="font-medium">
                {GUARD_BANNER_TEXT[message.guardBlocked]}
              </div>
              {message.guardRuleMatched && (
                <div className="mt-0.5 font-mono text-[10px] opacity-80 break-all">
                  命中規則：{message.guardRuleMatched}
                </div>
              )}
            </div>
          </div>
        )}
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
