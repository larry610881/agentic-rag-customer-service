"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSubmitFeedback } from "@/hooks/queries/use-feedback";
import { useChatStore } from "@/stores/use-chat-store";
import type { Rating } from "@/types/feedback";

const FEEDBACK_TAGS = [
  "答案不正確",
  "不完整",
  "沒回答問題",
  "語氣不好",
] as const;

interface FeedbackButtonsProps {
  messageId: string;
  conversationId: string;
  feedbackRating?: Rating;
}

export function FeedbackButtons({
  messageId,
  conversationId,
  feedbackRating,
}: FeedbackButtonsProps) {
  const [showCommentInput, setShowCommentInput] = useState(false);
  const [comment, setComment] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const submitFeedback = useSubmitFeedback();

  const handleFeedback = (rating: Rating) => {
    if (feedbackRating) return;

    if (rating === "thumbs_down") {
      setShowCommentInput(true);
      useChatStore.getState().setMessageFeedback(messageId, rating);
      return;
    }

    submitFeedback.mutate({
      conversation_id: conversationId,
      message_id: messageId,
      channel: "web",
      rating,
    });
  };

  const handleSubmitNegative = () => {
    submitFeedback.mutate({
      conversation_id: conversationId,
      message_id: messageId,
      channel: "web",
      rating: "thumbs_down",
      comment: comment || undefined,
      tags: selectedTags,
    });
    setShowCommentInput(false);
  };

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  if (feedbackRating && !showCommentInput) {
    return (
      <div className="mt-1 flex items-center gap-1">
        {feedbackRating === "thumbs_up" ? (
          <ThumbsUp className="h-3.5 w-3.5 text-primary" aria-label="已按讚" />
        ) : (
          <ThumbsDown
            className="h-3.5 w-3.5 text-destructive"
            aria-label="已按倒讚"
          />
        )}
        <span className="text-xs text-muted-foreground">感謝回饋</span>
      </div>
    );
  }

  return (
    <div className="mt-1">
      {!showCommentInput && (
        <div className="flex items-center gap-1" role="group" aria-label="回饋按鈕">
          <button
            type="button"
            onClick={() => handleFeedback("thumbs_up")}
            className={cn(
              "rounded p-1 text-muted-foreground transition-colors duration-150",
              "hover:bg-muted/50 hover:text-primary",
              "focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:outline-none",
            )}
            aria-label="有幫助"
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => handleFeedback("thumbs_down")}
            className={cn(
              "rounded p-1 text-muted-foreground transition-colors duration-150",
              "hover:bg-muted/50 hover:text-destructive",
              "focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:outline-none",
            )}
            aria-label="沒幫助"
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {showCommentInput && (
        <div className="mt-2 space-y-2">
          <div className="flex flex-wrap gap-1">
            {FEEDBACK_TAGS.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs transition-colors duration-150",
                  "focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:outline-none",
                  selectedTags.includes(tag)
                    ? "bg-destructive/10 text-destructive"
                    : "bg-muted text-muted-foreground hover:bg-muted/80",
                )}
              >
                {tag}
              </button>
            ))}
          </div>
          <div className="flex gap-1">
            <input
              type="text"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="告訴我們哪裡可以改善..."
              className="flex-1 rounded border bg-background px-2 py-1 text-xs focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:outline-none"
              aria-label="回饋評論"
            />
            <button
              type="button"
              onClick={handleSubmitNegative}
              className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground transition-colors duration-150 hover:bg-primary/90 active:scale-95"
            >
              送出
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
