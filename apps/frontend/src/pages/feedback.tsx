import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import {
  useFeedbackStats,
  useSatisfactionTrend,
  useTopIssues,
} from "@/hooks/queries/use-feedback";
import { FeedbackStatsSummary } from "@/features/feedback/components/feedback-stats-summary";
import { TokenPeriodSelector } from "@/features/feedback/components/token-period-selector";
import { Skeleton } from "@/components/ui/skeleton";
import { ROUTES } from "@/routes/paths";

const ChartSkeleton = () => <Skeleton className="h-[300px] w-full rounded-lg" />;

const SatisfactionTrendChart = lazy(() =>
  import("@/features/feedback/components/satisfaction-trend-chart").then(
    (m) => ({ default: m.SatisfactionTrendChart }),
  ),
);

const TopIssuesChart = lazy(() =>
  import("@/features/feedback/components/top-issues-chart").then((m) => ({
    default: m.TopIssuesChart,
  })),
);

function getDefaultRange() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const startDate = `${y}-${String(m).padStart(2, "0")}-01`;
  const next = new Date(y, m, 1);
  const endDate = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-01`;
  return { startDate, endDate };
}

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0, 0, 0.2, 1] } },
};

export default function FeedbackPage() {
  const defaults = getDefaultRange();
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);

  const stats = useFeedbackStats();
  const trend = useSatisfactionTrend(startDate, endDate);
  const issues = useTopIssues(startDate, endDate, 10);

  return (
    <motion.div
      className="flex flex-col gap-6 p-6"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={itemVariants} className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold font-heading tracking-wide text-primary">回饋分析</h2>
        <div className="flex items-center gap-3">
          <TokenPeriodSelector
            onChange={(s, e) => {
              setStartDate(s);
              setEndDate(e);
            }}
          />
          <Button variant="outline" asChild>
            <Link to={ROUTES.FEEDBACK_BROWSER}>回饋瀏覽器</Link>
          </Button>
        </div>
      </motion.div>
      <motion.div variants={itemVariants}>
        <FeedbackStatsSummary stats={stats.data} isLoading={stats.isLoading} />
      </motion.div>
      <motion.div variants={itemVariants} className="grid gap-6 lg:grid-cols-2">
        <Suspense fallback={<ChartSkeleton />}>
          <SatisfactionTrendChart
            data={trend.data}
            isLoading={trend.isLoading}
          />
        </Suspense>
        <Suspense fallback={<ChartSkeleton />}>
          <TopIssuesChart data={issues.data} isLoading={issues.isLoading} />
        </Suspense>
      </motion.div>
    </motion.div>
  );
}
