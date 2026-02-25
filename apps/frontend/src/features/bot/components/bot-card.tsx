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
import type { Bot } from "@/types/bot";

interface BotCardProps {
  bot: Bot;
}

export function BotCard({ bot }: BotCardProps) {
  return (
    <Link href={`/bots/${bot.id}`}>
      <Card className="transition-colors hover:bg-muted/50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">{bot.name}</CardTitle>
            <div className="flex gap-1">
              <Badge variant={bot.is_active ? "default" : "secondary"}>
                {bot.is_active ? "啟用" : "停用"}
              </Badge>
              <Badge variant="outline">
                {bot.knowledge_base_ids.length} KB
              </Badge>
            </div>
          </div>
          <CardDescription>{bot.description || "尚無描述"}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            更新於 {new Date(bot.updated_at).toLocaleDateString()}
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}
