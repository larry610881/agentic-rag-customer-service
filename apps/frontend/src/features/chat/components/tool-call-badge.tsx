import { Badge } from "@/components/ui/badge";
import { getToolLabel } from "@/constants/tool-labels";
import type { ToolCallInfo } from "@/types/chat";

interface ToolCallBadgeProps {
  toolCall: ToolCallInfo;
}

export function ToolCallBadge({ toolCall }: ToolCallBadgeProps) {
  // 優先使用 backend resolve 後的 label，fallback 至前端 TOOL_LABELS（i18n safety net）
  const display = toolCall.label || getToolLabel(toolCall.tool_name);
  return (
    <Badge variant="secondary" className="text-xs">
      {display}
    </Badge>
  );
}
