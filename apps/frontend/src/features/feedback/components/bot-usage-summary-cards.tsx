import { useMemo } from "react";
import { MessageSquare, ArrowDownToLine, ArrowUpFromLine } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ModelCostStat } from "@/types/feedback";

interface BotUsageSummaryCardsProps {
  data: ModelCostStat[] | undefined;
  isLoading: boolean;
}

export function BotUsageSummaryCards({ data, isLoading }: BotUsageSummaryCardsProps) {
  const summary = useMemo(() => {
    if (!data?.length) return { messages: 0, input: 0, output: 0 };
    return data.reduce(
      (acc, row) => ({
        messages: acc.messages + row.message_count,
        input: acc.input + row.input_tokens,
        output: acc.output + row.output_tokens,
      }),
      { messages: 0, input: 0, output: 0 },
    );
  }, [data]);

  const cards = [
    {
      title: "總訊息數",
      value: summary.messages,
      icon: MessageSquare,
    },
    {
      title: "總輸入 Tokens",
      value: summary.input,
      icon: ArrowDownToLine,
    },
    {
      title: "總輸出 Tokens",
      value: summary.output,
      icon: ArrowUpFromLine,
    },
  ];

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        {cards.map((c) => (
          <Card key={c.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{c.title}</CardTitle>
            </CardHeader>
            <CardContent><Skeleton className="h-8 w-24" /></CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {cards.map((c) => (
        <Card key={c.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{c.title}</CardTitle>
            <c.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{c.value.toLocaleString()}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
