import { Badge } from "@/components/ui/badge";
import { getToolLabel } from "@/constants/tool-labels";
import type { ToolCallInfo } from "@/types/chat";

interface ToolCallBadgeProps {
  toolCall: ToolCallInfo;
}

export function ToolCallBadge({ toolCall }: ToolCallBadgeProps) {
  return (
    <Badge variant="secondary" className="text-xs">
      {getToolLabel(toolCall.tool_name)}
    </Badge>
  );
}
