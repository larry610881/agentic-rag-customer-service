import { useMemo } from "react";
import { MessageSquare, Hash, FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { BotUsageStat } from "@/types/token-usage";
import { isChatType } from "@/types/token-usage";

interface UsageSummaryCardsProps {
  data: BotUsageStat[] | undefined;
  isLoading: boolean;
}

export function UsageSummaryCards({ data, isLoading }: UsageSummaryCardsProps) {
  const summary = useMemo(() => {
    if (!data?.length) return { chatCount: 0, ocrCount: 0, totalTokens: 0, totalCost: 0 };
    return data.reduce(
      (acc, row) => ({
        chatCount: acc.chatCount + (isChatType(row.request_type) ? row.message_count : 0),
        ocrCount: acc.ocrCount + (row.request_type === "ocr" ? row.message_count : 0),
        // 用 DB 的 total_tokens（含 cache_read + cache_creation），
        // 與本月額度頁 total_used_in_cycle 對齊；原本 input+output 漏算 cache tokens
        totalTokens: acc.totalTokens + row.total_tokens,
        totalCost: acc.totalCost + row.estimated_cost,
      }),
      { chatCount: 0, ocrCount: 0, totalTokens: 0, totalCost: 0 },
    );
  }, [data]);

  const cards = [
    { title: "對話次數", value: summary.chatCount.toLocaleString(), icon: MessageSquare },
    { title: "文件處理次數", value: summary.ocrCount.toLocaleString(), icon: FileText },
    { title: "總 Tokens", value: summary.totalTokens.toLocaleString(), icon: Hash },
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
            <p className="text-2xl font-bold">{c.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
