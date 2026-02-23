"use client";

import { CitationCard } from "@/features/chat/components/citation-card";
import type { Source } from "@/types/chat";

interface CitationListProps {
  sources: Source[];
}

export function CitationList({ sources }: CitationListProps) {
  if (sources.length === 0) return null;

  return (
    <div className="ml-0 flex flex-col gap-1 sm:ml-4">
      <p className="text-xs font-medium text-muted-foreground">Sources</p>
      {sources.map((source, i) => (
        <CitationCard key={`${source.document_name}-${i}`} source={source} index={i} />
      ))}
    </div>
  );
}
