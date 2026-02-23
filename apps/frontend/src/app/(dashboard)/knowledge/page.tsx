"use client";

import { KnowledgeBaseList } from "@/features/knowledge/components/knowledge-base-list";
import { CreateKbDialog } from "@/features/knowledge/components/create-kb-dialog";

export default function KnowledgePage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Knowledge Bases</h2>
        <CreateKbDialog />
      </div>
      <KnowledgeBaseList />
    </div>
  );
}
