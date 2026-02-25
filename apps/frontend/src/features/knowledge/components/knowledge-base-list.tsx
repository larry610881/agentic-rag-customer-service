"use client";

import { useKnowledgeBases } from "@/hooks/queries/use-knowledge-bases";
import { KnowledgeBaseCard } from "@/features/knowledge/components/knowledge-base-card";
import { Skeleton } from "@/components/ui/skeleton";

export function KnowledgeBaseList() {
  const { data: knowledgeBases, isLoading, isError } = useKnowledgeBases();

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-36 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <p className="text-destructive">載入知識庫失敗。</p>;
  }

  if (!knowledgeBases || knowledgeBases.length === 0) {
    return (
      <p className="text-muted-foreground">
        尚無知識庫，請建立一個來開始使用。
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {knowledgeBases.map((kb) => (
        <KnowledgeBaseCard key={kb.id} knowledgeBase={kb} />
      ))}
    </div>
  );
}
