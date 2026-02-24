"use client";

import { Bot as BotIcon } from "lucide-react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useBots } from "@/hooks/queries/use-bots";
import { useChatStore } from "@/stores/use-chat-store";
import type { Bot } from "@/types/bot";

export function BotSelector() {
  const { data: bots, isLoading, isError } = useBots();
  const selectBot = useChatStore((s) => s.selectBot);

  const activeBots = bots?.filter((b) => b.is_active) ?? [];

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 p-8">
        <Skeleton className="h-8 w-64" />
        <div className="grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8">
        <p className="text-sm text-destructive">無法載入機器人</p>
        <p className="text-xs text-muted-foreground">請重新整理頁面後再試。</p>
      </div>
    );
  }

  if (activeBots.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8">
        <BotIcon className="h-10 w-10 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">目前沒有可用的機器人</p>
        <p className="text-xs text-muted-foreground">
          請先到機器人頁面建立並啟用一個機器人。
        </p>
      </div>
    );
  }

  const handleSelect = (bot: Bot) => {
    selectBot(bot.id, bot.name);
  };

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h2 className="text-lg font-semibold">選擇一個機器人開始對話</h2>
        <p className="text-sm text-muted-foreground">
          從下方選擇一個可用的機器人
        </p>
      </div>
      <div className="grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
        {activeBots.map((bot) => (
          <button key={bot.id} type="button" onClick={() => handleSelect(bot)} className="text-left">
            <Card className="h-full cursor-pointer transition-all duration-200 hover:bg-muted/50 hover:shadow-md">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{bot.name}</CardTitle>
                  <Badge variant="outline">
                    {bot.knowledge_base_ids.length} KB
                  </Badge>
                </div>
                <CardDescription>
                  {bot.description || "尚無描述"}
                </CardDescription>
              </CardHeader>
            </Card>
          </button>
        ))}
      </div>
    </div>
  );
}
