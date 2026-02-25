"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  useFeedbackStats,
  useSatisfactionTrend,
  useTopIssues,
  useTokenCostStats,
} from "@/hooks/queries/use-feedback";
import { FeedbackStatsSummary } from "@/features/feedback/components/feedback-stats-summary";
import { SatisfactionTrendChart } from "@/features/feedback/components/satisfaction-trend-chart";
import { TopIssuesChart } from "@/features/feedback/components/top-issues-chart";
import { TokenCostTable } from "@/features/feedback/components/token-cost-table";

export default function FeedbackPage() {
  const stats = useFeedbackStats();
  const trend = useSatisfactionTrend(30);
  const issues = useTopIssues(30, 10);
  const costs = useTokenCostStats(30);

  return (
    <div className="h-full overflow-auto flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">回饋分析</h2>
        <Button variant="outline" asChild>
          <Link href="/feedback/browser">差評瀏覽器</Link>
        </Button>
      </div>
      <FeedbackStatsSummary stats={stats.data} isLoading={stats.isLoading} />
      <div className="grid gap-6 lg:grid-cols-2">
        <SatisfactionTrendChart data={trend.data} isLoading={trend.isLoading} />
        <TopIssuesChart data={issues.data} isLoading={issues.isLoading} />
      </div>
      <TokenCostTable data={costs.data} isLoading={costs.isLoading} />
    </div>
  );
}
