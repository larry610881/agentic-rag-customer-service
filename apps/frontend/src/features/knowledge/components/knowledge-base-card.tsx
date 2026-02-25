"use client";

import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { KnowledgeBase } from "@/types/knowledge";

interface KnowledgeBaseCardProps {
  knowledgeBase: KnowledgeBase;
}

export function KnowledgeBaseCard({ knowledgeBase }: KnowledgeBaseCardProps) {
  return (
    <Link href={`/knowledge/${knowledgeBase.id}`}>
      <Card className="transition-colors hover:bg-muted/50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">{knowledgeBase.name}</CardTitle>
            <Badge variant="secondary">{knowledgeBase.document_count} 份文件</Badge>
          </div>
          <CardDescription>{knowledgeBase.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            更新於 {new Date(knowledgeBase.updated_at).toLocaleDateString()}
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}
