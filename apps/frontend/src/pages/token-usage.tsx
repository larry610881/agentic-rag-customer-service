import { useState } from "react";
import { motion } from "framer-motion";
import { useBotUsage, useDailyUsage } from "@/hooks/queries/use-usage";
import { TokenPeriodSelector } from "@/features/feedback/components/token-period-selector";
import { UsageSummaryCards } from "@/features/usage/components/usage-summary-cards";
import { UsageDailyLineChart } from "@/features/usage/components/usage-daily-line-chart";
import { UsageBotPieChart } from "@/features/usage/components/usage-bot-pie-chart";
import { UsageBotBarChart } from "@/features/usage/components/usage-bot-bar-chart";

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

export default function TokenUsagePage() {
  const defaults = getDefaultRange();
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);

  const botUsage = useBotUsage(startDate, endDate);
  const dailyUsage = useDailyUsage(startDate, endDate);

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
          onChange={(s, e) => {
            setStartDate(s);
            setEndDate(e);
          }}
        />
      </motion.div>

      <motion.div variants={itemVariants}>
        <UsageSummaryCards data={botUsage.data} isLoading={botUsage.isLoading} />
      </motion.div>

      <motion.div variants={itemVariants}>
        <UsageDailyLineChart data={dailyUsage.data} isLoading={dailyUsage.isLoading} />
      </motion.div>

      <motion.div variants={itemVariants} className="grid gap-6 lg:grid-cols-2">
        <UsageBotPieChart data={botUsage.data} isLoading={botUsage.isLoading} />
        <UsageBotBarChart data={botUsage.data} isLoading={botUsage.isLoading} />
      </motion.div>
    </motion.div>
  );
}
