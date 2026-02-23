"use client";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import type { Source } from "@/types/chat";

interface CitationCardProps {
  source: Source;
  index: number;
}

export function CitationCard({ source, index }: CitationCardProps) {
  return (
    <Collapsible>
      <CollapsibleTrigger className="flex w-full items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted">
        <Badge variant="outline">{index + 1}</Badge>
        <span className="truncate font-medium">{source.document_name}</span>
        <span className="ml-auto text-xs text-muted-foreground">
          {Math.round(source.score * 100)}%
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 py-2">
        <p className="text-sm text-muted-foreground">{source.content_snippet}</p>
      </CollapsibleContent>
    </Collapsible>
  );
}
