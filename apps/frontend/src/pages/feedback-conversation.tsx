import { useParams } from "react-router-dom";
import { useConversation } from "@/hooks/queries/use-conversations";
import {
  useFeedbackByConversation,
  useUpdateFeedbackTags,
} from "@/hooks/queries/use-feedback";
import { ConversationReplay } from "@/features/feedback/components/conversation-replay";
import { PageBreadcrumb } from "@/components/shared/page-breadcrumb";
import { ROUTES } from "@/routes/paths";

export default function FeedbackConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const conversation = useConversation(conversationId!);
  const feedbacks = useFeedbackByConversation(conversationId!);
  const updateTags = useUpdateFeedbackTags();

  const messages = conversation.data?.messages.map((m) => ({
    id: m.id,
    role: m.role as "user" | "assistant",
    content: m.content,
    retrieved_chunks: m.retrieved_chunks,
    latency_ms: m.latency_ms,
  }));

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageBreadcrumb
        items={[
          { label: "對話回饋", to: ROUTES.FEEDBACK_BROWSER },
          { label: conversationId ?? "對話回放" },
        ]}
      />
      <div className="flex items-center gap-3">
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
