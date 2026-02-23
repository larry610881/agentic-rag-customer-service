"use client";

import { Badge } from "@/components/ui/badge";
import type { ToolCallInfo } from "@/types/chat";

interface ToolCallBadgeProps {
  toolCall: ToolCallInfo;
}

export function ToolCallBadge({ toolCall }: ToolCallBadgeProps) {
  return (
    <Badge variant="secondary" className="text-xs">
      {toolCall.tool_name}
    </Badge>
  );
}
