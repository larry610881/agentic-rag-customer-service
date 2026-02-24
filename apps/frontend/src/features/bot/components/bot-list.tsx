"use client";

import { useBots } from "@/hooks/queries/use-bots";
import { BotCard } from "@/features/bot/components/bot-card";
import { Skeleton } from "@/components/ui/skeleton";

export function BotList() {
  const { data: bots, isLoading, isError } = useBots();

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
    return <p className="text-destructive">Failed to load bots.</p>;
  }

  if (!bots || bots.length === 0) {
    return (
      <p className="text-muted-foreground">
        No bots yet. Create one to get started.
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {bots.map((bot) => (
        <BotCard key={bot.id} bot={bot} />
      ))}
    </div>
  );
}
