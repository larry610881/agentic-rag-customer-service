import { useMemo, useState } from "react";
import type { Variants } from "framer-motion";
import { motion } from "framer-motion";
import { useBillingDashboard } from "@/hooks/queries/use-billing-dashboard";
import { BillingRevenueLineChart } from "@/features/admin/components/billing-revenue-line-chart";
import { BillingByPlanPieChart } from "@/features/admin/components/billing-by-plan-pie-chart";
import { BillingTopTenantsTable } from "@/features/admin/components/billing-top-tenants-table";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatCurrency } from "@/lib/format-currency";

const containerVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.3, ease: [0, 0, 0.2, 1] as const },
  },
};

function buildCycleOptions(): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i < 24; i += 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = i === 0 ? `${value}（當月）` : value;
    opts.push({ value, label });
  }
  return opts;
}

export default function AdminBillingPage() {
  const cycleOptions = useMemo(buildCycleOptions, []);
  const currentCycle = cycleOptions[0]?.value ?? "";
  const sixMonthsBack = cycleOptions[5]?.value ?? cycleOptions[0]?.value ?? "";
  const [end, setEnd] = useState<string>(currentCycle);
  const [start, setStart] = useState<string>(sixMonthsBack);

  const { data, isLoading, isError, refetch } = useBillingDashboard({
    start,
    end,
    topN: 10,
  });

  const monthsCount = data?.monthly_revenue.length ?? 0;
  const avgMonthly = useMemo(() => {
    if (!data || monthsCount === 0) return "0";
    return (Number(data.total_revenue) / monthsCount).toFixed(2);
  }, [data, monthsCount]);

  const currentMonthRevenue = useMemo(() => {
    if (!data?.monthly_revenue.length) return "0";
    const last = data.monthly_revenue[data.monthly_revenue.length - 1];
    return last.total_amount;
  }, [data]);

  // start 不可大於 end
  const validStartOptions = cycleOptions.filter((o) => o.value <= end);
  const validEndOptions = cycleOptions.filter((o) => o.value >= start);

  return (
    <motion.div
      className="flex flex-col gap-6 p-6"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.div
        variants={itemVariants}
        className="flex flex-wrap items-center justify-between gap-3"
      >
        <div>
          <h1 className="text-2xl font-bold tracking-tight">收益儀表板</h1>
          <p className="text-muted-foreground">
            Token-Gov 自動續約累計營收（系統管理員專用）
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={start} onValueChange={setStart}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="起始月" />
            </SelectTrigger>
            <SelectContent>
              {validStartOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-muted-foreground">→</span>
          <Select value={end} onValueChange={setEnd}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="結束月" />
            </SelectTrigger>
            <SelectContent>
              {validEndOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => refetch()}>
            重新整理
          </Button>
        </div>
      </motion.div>

      {isError && (
        <Card>
          <CardContent className="py-12 text-center text-destructive">
            載入失敗，請稍後重試
          </CardContent>
        </Card>
      )}

      <motion.div
        variants={itemVariants}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <SummaryCard
          label="總營收"
          value={data ? formatCurrency(data.total_revenue) : "—"}
        />
        <SummaryCard
          label="總交易數"
          value={data ? String(data.total_transactions) : "—"}
        />
        <SummaryCard
          label="平均月營收"
          value={data ? formatCurrency(avgMonthly) : "—"}
        />
        <SummaryCard
          label="本月營收"
          value={data ? formatCurrency(currentMonthRevenue) : "—"}
        />
      </motion.div>

      <motion.div variants={itemVariants} className="grid gap-6 lg:grid-cols-2">
        <BillingRevenueLineChart
          data={data?.monthly_revenue}
          isLoading={isLoading}
        />
        <BillingByPlanPieChart data={data?.by_plan} isLoading={isLoading} />
      </motion.div>

      <motion.div variants={itemVariants}>
        <BillingTopTenantsTable
          data={data?.top_tenants}
          isLoading={isLoading}
        />
      </motion.div>
    </motion.div>
  );
}

type SummaryCardProps = {
  label: string;
  value: string;
};

function SummaryCard({ label, value }: SummaryCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}
