"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const ISSUE_SUGGESTIONS: Record<string, string> = {
  too_short: "較多分塊過短（< 50 字），建議增大 chunk_size 或調整分塊策略。",
  high_variance: "分塊長度差異過大，建議降低 chunk_size 使長度更均勻。",
  mid_sentence_break: "較多分塊在句子中間斷開，建議增大 chunk_overlap 或改用語義分塊。",
};

interface QualityTooltipProps {
  issues: string[];
  children: React.ReactNode;
}

export function QualityTooltip({ issues, children }: QualityTooltipProps) {
  if (issues.length === 0) {
    return <>{children}</>;
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent className="max-w-xs" data-testid="quality-tooltip">
          <ul className="list-disc pl-4 text-xs">
            {issues.map((issue) => (
              <li key={issue}>
                {ISSUE_SUGGESTIONS[issue] ?? issue}
              </li>
            ))}
          </ul>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
