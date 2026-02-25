"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useConversation } from "@/hooks/queries/use-conversations";
import {
  useFeedbackByConversation,
  useUpdateFeedbackTags,
} from "@/hooks/queries/use-feedback";
import { ConversationReplay } from "@/features/feedback/components/conversation-replay";

export default function FeedbackConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = use(params);
  const conversation = useConversation(conversationId);
  const feedbacks = useFeedbackByConversation(conversationId);
  const updateTags = useUpdateFeedbackTags();

  const messages = conversation.data?.messages.map((m) => ({
    id: m.id,
    role: m.role as "user" | "assistant",
    content: m.content,
    retrieved_chunks: m.retrieved_chunks,
    latency_ms: m.latency_ms,
  }));

  return (
    <div className="h-full overflow-auto flex flex-col gap-6 p-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/feedback/browser">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-semibold">對話回放</h2>
        <span className="text-sm text-muted-foreground">
          {conversationId}
        </span>
      </div>
      <ConversationReplay
        messages={messages}
        feedbacks={feedbacks.data}
        isLoading={conversation.isLoading || feedbacks.isLoading}
        onUpdateTags={(feedbackId, tags) =>
          updateTags.mutate({ feedbackId, tags })
        }
        isUpdatingTags={updateTags.isPending}
      />
    </div>
  );
}
