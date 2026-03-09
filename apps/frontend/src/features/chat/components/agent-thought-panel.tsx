import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { getToolLabel } from "@/constants/tool-labels";
import { ToolCallBadge } from "@/features/chat/components/tool-call-badge";
import type { ToolCallInfo } from "@/types/chat";

const CIRCLED_NUMBERS = ["\u2460", "\u2461", "\u2462", "\u2463", "\u2464", "\u2465", "\u2466", "\u2467", "\u2468", "\u2469"];
const getCircledNumber = (index: number): string =>
  CIRCLED_NUMBERS[index] || `(${index + 1})`;

interface AgentThoughtPanelProps {
  toolCalls: ToolCallInfo[];
}

export function AgentThoughtPanel({ toolCalls }: AgentThoughtPanelProps) {
  if (toolCalls.length === 0) return null;

  return (
    <Collapsible className="ml-0 sm:ml-4">
      <CollapsibleTrigger className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
        <span>Agent 操作（{toolCalls.length} 個工具）</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1 flex flex-col gap-2">
        {toolCalls.map((tc, i) => (
          <div key={`${tc.tool_name}-${i}`} className="flex items-start gap-2">
            <span className="text-xs text-muted-foreground shrink-0">
              {getCircledNumber(i)}
            </span>
            <ToolCallBadge toolCall={tc} />
            {tc.reasoning && (
              <span className="text-xs text-muted-foreground">
                {tc.reasoning}
              </span>
            )}
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
