"use client";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ToolCallBadge } from "@/features/chat/components/tool-call-badge";
import type { ToolCallInfo } from "@/types/chat";

interface AgentThoughtPanelProps {
  toolCalls: ToolCallInfo[];
}

export function AgentThoughtPanel({ toolCalls }: AgentThoughtPanelProps) {
  if (toolCalls.length === 0) return null;

  return (
    <Collapsible className="ml-0 sm:ml-4">
      <CollapsibleTrigger className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
        <span>Agent Actions ({toolCalls.length})</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1 flex flex-col gap-2">
        {toolCalls.map((tc, i) => (
          <div key={`${tc.tool_name}-${i}`} className="flex items-start gap-2">
            <ToolCallBadge toolCall={tc} />
            <span className="text-xs text-muted-foreground">{tc.reasoning}</span>
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
