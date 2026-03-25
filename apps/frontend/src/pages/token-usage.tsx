import { useState } from "react";
import { motion } from "framer-motion";
import { useBotUsage, useDailyUsage, useMonthlyUsage } from "@/hooks/queries/use-usage";
import { TokenPeriodSelector } from "@/features/feedback/components/token-period-selector";
import { UsageSummaryCards } from "@/features/usage/components/usage-summary-cards";
import { UsageTrendLineChart } from "@/features/usage/components/usage-daily-line-chart";
import { UsagePieChart } from "@/features/usage/components/usage-bot-pie-chart";
import { UsageMonthlyBarChart } from "@/features/usage/components/usage-bot-bar-chart";
import type { DailyUsageStat, MonthlyUsageStat } from "@/types/token-usage";

function getDefaultRange() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const startDate = `${y}-${String(m).padStart(2, "0")}-01`;
  const next = new Date(y, m, 1);
  const endDate = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-01`;
  return { startDate, endDate };
}

function toTrendData(
  mode: "month" | "year",
  daily: DailyUsageStat[] | undefined,
  monthly: MonthlyUsageStat[] | undefined,
) {
  if (mode === "month" && daily?.length) {
    return daily.map((d) => ({
      label: d.date.slice(5), // "03-25"
      total_tokens: d.total_tokens,
      input_tokens: d.input_tokens,
      output_tokens: d.output_tokens,
    }));
  }
  if (mode === "year" && monthly?.length) {
    return monthly.map((d) => ({
      label: d.month.slice(5) + "月", // "03月"
      total_tokens: d.total_tokens,
      input_tokens: d.input_tokens,
      output_tokens: d.output_tokens,
    }));
  }
  return undefined;
}

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0, 0, 0.2, 1] } },
};

export default function TokenUsagePage() {
  const defaults = getDefaultRange();
  const [mode, setMode] = useState<"month" | "year">("month");
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);

  const botUsage = useBotUsage(startDate, endDate);
  const dailyUsage = useDailyUsage(startDate, endDate);
  const monthlyUsage = useMonthlyUsage(startDate, endDate);

  const trendData = toTrendData(mode, dailyUsage.data, monthlyUsage.data);
  const trendLoading = mode === "month" ? dailyUsage.isLoading : monthlyUsage.isLoading;

  return (
    <motion.div
      className="flex flex-col gap-6 p-6"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={itemVariants} className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold font-heading tracking-wide text-primary">
          Token 用量
        </h2>
        <TokenPeriodSelector
          onChange={(s, e, m) => {
            setStartDate(s);
            setEndDate(e);
            setMode(m);
          }}
        />
      </motion.div>

      <motion.div variants={itemVariants}>
        <UsageSummaryCards data={botUsage.data} isLoading={botUsage.isLoading} />
      </motion.div>

      <motion.div variants={itemVariants}>
        <UsageTrendLineChart data={trendData} isLoading={trendLoading} mode={mode} />
      </motion.div>

      {mode === "year" ? (
        <motion.div variants={itemVariants} className="grid gap-6 lg:grid-cols-2">
          <UsageMonthlyBarChart data={monthlyUsage.data} isLoading={monthlyUsage.isLoading} />
          <UsagePieChart data={botUsage.data} isLoading={botUsage.isLoading} />
        </motion.div>
      ) : (
        <motion.div variants={itemVariants}>
          <UsagePieChart data={botUsage.data} isLoading={botUsage.isLoading} />
        </motion.div>
      )}
    </motion.div>
  );
}
