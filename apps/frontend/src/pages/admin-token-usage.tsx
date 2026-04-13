import { useMemo, useState } from "react";
import type { Variants } from "framer-motion";
import { motion } from "framer-motion";
import { useSystemTokenUsage } from "@/hooks/queries/use-token-usage";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { TokenUsagePieChart } from "@/features/admin/components/token-usage-pie-chart";
import { TokenUsageBarChart } from "@/features/admin/components/token-usage-bar-chart";
import { TokenUsageDetailTable } from "@/features/admin/components/token-usage-detail-table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { REQUEST_TYPE_LABELS } from "@/types/token-usage";

const containerVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0, 0, 0.2, 1] as const } },
};

const TYPE_FILTER_OPTIONS = [
  { value: "all", label: "全部類型" },
  ...Object.entries(REQUEST_TYPE_LABELS)
    .filter(([k]) => k !== "agent") // skip legacy alias
    .map(([value, label]) => ({ value, label })),
];

export default function AdminTokenUsagePage() {
  const [days, setDays] = useState(30);
  const [tenantId, setTenantId] = useState<string | undefined>();
  const [typeFilter, setTypeFilter] = useState("all");
  const { data: rawData, isLoading } = useSystemTokenUsage(days, tenantId);

  const data = useMemo(() => {
    if (!rawData || typeFilter === "all") return rawData;
    return rawData.filter((row) => {
      if (typeFilter === "chat_web") {
        return row.request_type === "chat_web" || row.request_type === "agent";
      }
      return row.request_type === typeFilter;
    });
  }, [rawData, typeFilter]);

  return (
    <motion.div
      className="flex flex-col gap-6 p-6"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={itemVariants} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Token 用量</h1>
          <p className="text-muted-foreground">跨租戶 Token 使用量與成本分析</p>
        </div>
        <div className="flex items-center gap-3">
          <AdminTenantFilter value={tenantId} onChange={setTenantId} />
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPE_FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">最近 7 天</SelectItem>
              <SelectItem value="14">最近 14 天</SelectItem>
              <SelectItem value="30">最近 30 天</SelectItem>
              <SelectItem value="90">最近 90 天</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </motion.div>

      <motion.div variants={itemVariants} className="grid gap-6 lg:grid-cols-2">
        <TokenUsagePieChart data={data} isLoading={isLoading} />
        <TokenUsageBarChart data={data} isLoading={isLoading} />
      </motion.div>

      <motion.div variants={itemVariants}>
        <TokenUsageDetailTable data={data} isLoading={isLoading} />
      </motion.div>
    </motion.div>
  );
}
