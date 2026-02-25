"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ThumbsUp, ThumbsDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { TagEditor } from "./tag-editor";
import type { FeedbackResponse } from "@/types/feedback";

interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrieved_chunks?: Record<string, unknown>[] | null;
  latency_ms?: number | null;
}

interface ConversationReplayProps {
  messages: ConversationMessage[] | undefined;
  feedbacks: FeedbackResponse[] | undefined;
  isLoading: boolean;
  onUpdateTags?: (feedbackId: string, tags: string[]) => void;
  isUpdatingTags?: boolean;
}

export function ConversationReplay({
  messages,
  feedbacks,
  isLoading,
  onUpdateTags,
  isUpdatingTags,
}: ConversationReplayProps) {
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>對話回放</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!messages?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>對話回放</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-8 text-center text-muted-foreground">
            找不到對話記錄
          </p>
        </CardContent>
      </Card>
    );
  }

  function toggleChunks(msgId: string) {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) next.delete(msgId);
      else next.add(msgId);
      return next;
    });
  }

  function getFeedbackForMessage(messageId: string) {
    return feedbacks?.find((f) => f.message_id === messageId);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>對話回放</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {messages.map((msg) => {
          const fb = getFeedbackForMessage(msg.id);
          const isExpanded = expandedChunks.has(msg.id);
          const hasChunks =
            msg.retrieved_chunks && msg.retrieved_chunks.length > 0;

          return (
            <div
              key={msg.id}
              className={cn(
                "rounded-lg border p-3",
                msg.role === "user" ? "bg-muted/50" : "bg-background",
              )}
            >
              <div className="mb-1 flex items-center gap-2">
                <Badge variant={msg.role === "user" ? "outline" : "secondary"}>
                  {msg.role === "user" ? "使用者" : "AI"}
                </Badge>
                {msg.latency_ms != null && (
                  <span className="text-xs text-muted-foreground">
                    {msg.latency_ms}ms
                  </span>
                )}
                {fb && (
                  <span className="ml-auto">
                    {fb.rating === "thumbs_up" ? (
                      <ThumbsUp className="h-4 w-4 text-green-600" />
                    ) : (
                      <ThumbsDown className="h-4 w-4 text-red-500" />
                    )}
                  </span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
              {hasChunks && (
                <div className="mt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 gap-1 px-2 text-xs"
                    onClick={() => toggleChunks(msg.id)}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    檢索片段 ({msg.retrieved_chunks!.length})
                  </Button>
                  {isExpanded && (
                    <div className="mt-1 space-y-1">
                      {msg.retrieved_chunks!.map((chunk, i) => (
                        <pre
                          key={i}
                          className="overflow-x-auto rounded bg-muted p-2 text-xs"
                        >
                          {JSON.stringify(chunk, null, 2)}
                        </pre>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {fb && onUpdateTags && (
                <div className="mt-2 border-t pt-2">
                  <p className="mb-1 text-xs text-muted-foreground">
                    回饋標籤
                  </p>
                  <TagEditor
                    tags={fb.tags}
                    onSave={(tags) => onUpdateTags(fb.id, tags)}
                    isSaving={isUpdatingTags}
                  />
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
