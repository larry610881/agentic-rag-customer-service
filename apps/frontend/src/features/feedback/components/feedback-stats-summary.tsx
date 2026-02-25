"use client";

import { ThumbsUp, ThumbsDown, MessageSquare, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { FeedbackStats } from "@/types/feedback";

interface FeedbackStatsSummaryProps {
  stats: FeedbackStats | undefined;
  isLoading: boolean;
}

export function FeedbackStatsSummary({
  stats,
  isLoading,
}: FeedbackStatsSummaryProps) {
  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-4" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    {
      title: "總回饋數",
      value: stats?.total ?? 0,
      icon: MessageSquare,
    },
    {
      title: "正面回饋",
      value: stats?.thumbs_up ?? 0,
      icon: ThumbsUp,
    },
    {
      title: "負面回饋",
      value: stats?.thumbs_down ?? 0,
      icon: ThumbsDown,
    },
    {
      title: "滿意度",
      value: `${(stats?.satisfaction_rate ?? 0).toFixed(1)}%`,
      icon: TrendingUp,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
            <card.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{card.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
