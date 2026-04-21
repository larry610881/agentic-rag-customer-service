import { useNavigate } from "react-router-dom";
import { ArrowRight, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format-date";
import type { ConversationSearchResult } from "@/hooks/queries/use-conversation-search";

interface CardProps {
  item: ConversationSearchResult;
}

const MATCH_BADGE_CLASS: Record<string, string> = {
  keyword: "bg-blue-500/15 text-blue-700",
  semantic: "bg-purple-500/15 text-purple-700",
};

export function ConversationSearchResultCard({ item }: CardProps) {
  const navigate = useNavigate();
  const matchedLabel = item.matched_via === "keyword" ? "🔍 關鍵字" : "🧠 意思";
  const scoreText =
    item.score !== null ? ` · 相似度 ${item.score.toFixed(3)}` : "";

  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <p className="text-sm leading-relaxed">{item.summary || "—"}</p>
          </div>
          <Badge className={MATCH_BADGE_CLASS[item.matched_via] ?? ""}>
            {matchedLabel}
            {scoreText}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            {item.tenant_name || "—"}
          </span>
          {item.bot_id && (
            <span className="font-mono">Bot {item.bot_id.substring(0, 8)}</span>
          )}
          <span>{item.message_count} messages</span>
          {item.first_message_at && (
            <span>
              {formatDateTime(item.first_message_at)}
              {item.last_message_at &&
                item.last_message_at !== item.first_message_at &&
                ` ~ ${formatDateTime(item.last_message_at)}`}
            </span>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              navigate(
                `/admin/observability?conversation_id=${item.conversation_id}`,
              )
            }
          >
            跳 Trace 視圖
            <ArrowRight className="ml-1 h-3 w-3" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
