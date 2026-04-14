import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/format-date";
import type { ConversationSummary } from "@/types/conversation";

interface ConversationItemProps {
  conversation: ConversationSummary;
  isActive: boolean;
  onClick: () => void;
}

function shortenId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}...` : id;
}

export function ConversationItem({
  conversation,
  isActive,
  onClick,
}: ConversationItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-md px-3 py-2 text-left text-sm transition-colors duration-150",
        "hover:bg-muted/50",
        isActive && "bg-muted font-medium border-l-2 border-primary",
      )}
      aria-current={isActive ? "true" : undefined}
    >
      <div className="truncate text-foreground">
        {shortenId(conversation.id)}
      </div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        {formatDate(conversation.created_at)}
      </div>
    </button>
  );
}
