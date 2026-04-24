import { useMemo, useState } from "react";
import type { Variants } from "framer-motion";
import { motion } from "framer-motion";
import { useAdminTenantsQuotas } from "@/hooks/queries/use-admin-quotas";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import { getCategoryShortLabel } from "@/constants/usage-categories";

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

function formatTokens(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function buildCycleOptions(): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i < 12; i += 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = i === 0 ? `${value}（當月）` : value;
    opts.push({ value, label });
  }
  return opts;
}

function categoryBadge(included: string[] | null) {
  if (included === null) {
    return <Badge variant="secondary">全部計入</Badge>;
  }
  if (included.length === 0) {
    return (
      <Badge variant="outline" className="border-orange-500 text-orange-600">
        全部不計入
      </Badge>
    );
  }
  const visible = included.slice(0, 3);
  const overflow = included.length - visible.length;
  return (
    <div className="flex flex-wrap gap-1">
      {visible.map((c) => (
        <Badge key={c} variant="outline">
          {getCategoryShortLabel(c)}
        </Badge>
      ))}
      {overflow > 0 && (
        <Badge variant="outline">+{overflow}</Badge>
      )}
    </div>
  );
}

function addonBadge(remaining: number, hasLedger: boolean) {
  if (!hasLedger) {
    return <span className="text-muted-foreground">—</span>;
  }
  if (remaining > 0) {
    return (
      <Badge className="bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/20">
        +{formatTokens(remaining)}
      </Badge>
    );
  }
  if (remaining === 0) {
    return <Badge variant="secondary">0</Badge>;
  }
  return (
    <Badge variant="destructive">{formatTokens(remaining)}</Badge>
  );
}

export default function AdminQuotaOverviewPage() {
  const cycleOptions = useMemo(buildCycleOptions, []);
  const [cycle, setCycle] = useState<string>(cycleOptions[0]?.value ?? "");

  const { data, isLoading, isError, refetch } = useAdminTenantsQuotas(cycle);

  const sorted = useMemo(() => {
    if (!data) return [];
    return [...data].sort(
      (a, b) => b.total_audit_in_cycle - a.total_audit_in_cycle,
    );
  }, [data]);

  const summary = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        tenantCount: 0,
        activeLedgers: 0,
        baseUsedPct: 0,
        addonTotal: 0,
        auditTotal: 0,
        absorbedTotal: 0,
      };
    }
    let activeLedgers = 0;
    let baseUsedSum = 0;
    let baseTotalSum = 0;
    let addonTotal = 0;
    let auditTotal = 0;
    let absorbedTotal = 0;
    for (const item of data) {
      if (item.has_ledger) activeLedgers += 1;
      baseUsedSum += item.base_total - item.base_remaining;
      baseTotalSum += item.base_total;
      addonTotal += item.addon_remaining;
      auditTotal += item.total_audit_in_cycle;
      absorbedTotal += item.platform_absorbed_tokens;
    }
    const baseUsedPct =
      baseTotalSum > 0 ? Math.round((baseUsedSum / baseTotalSum) * 100) : 0;
    return {
      tenantCount: data.length,
      activeLedgers,
      baseUsedPct,
      addonTotal,
      auditTotal,
      absorbedTotal,
    };
  }, [data]);

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
          <h1 className="text-2xl font-bold tracking-tight">額度總覽</h1>
          <p className="text-muted-foreground">
            跨租戶 Token 額度與使用狀況（系統管理員專用）
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={cycle} onValueChange={setCycle}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {cycleOptions.map((opt) => (
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

      <motion.div
        variants={itemVariants}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6"
      >
        <SummaryCard label="租戶總數" value={summary.tenantCount.toString()} />
        <SummaryCard
          label="本月已啟用 Ledger"
          value={`${summary.activeLedgers} / ${summary.tenantCount}`}
        />
        <SummaryCard
          label="全租戶 Base 用量"
          value={`${summary.baseUsedPct}%`}
        />
        <SummaryCard
          label="全租戶 Addon 餘額"
          value={formatTokens(summary.addonTotal)}
          highlight={summary.addonTotal < 0 ? "destructive" : undefined}
        />
        <SummaryCard
          label="全平台審計總量"
          value={formatTokens(summary.auditTotal)}
        />
        <SummaryCard
          label="全平台吸收量"
          value={formatTokens(summary.absorbedTotal)}
          highlight={summary.absorbedTotal > 0 ? "destructive" : undefined}
        />
      </motion.div>

      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>租戶額度明細</CardTitle>
          </CardHeader>
          <CardContent>
            {isError ? (
              <div className="py-12 text-center text-destructive">
                載入失敗，請稍後重試
              </div>
            ) : isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : sorted.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                該月份尚無資料
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>租戶</TableHead>
                    <TableHead>方案</TableHead>
                    <TableHead className="min-w-[200px]">
                      <span className="inline-flex items-center gap-1">
                        Base 進度
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="text-xs">
                              <b>Base 進度</b> = base_total - base_remaining
                            </p>
                            <p className="text-xs mt-1">
                              從 token_usage_records 即時算出，結構上永遠 ≡ 計費總量
                              min(billable, base_total)，不會 drift。
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </span>
                    </TableHead>
                    <TableHead>Addon 餘額</TableHead>
                    <TableHead>
                      <span className="inline-flex items-center gap-1">
                        計費 / 審計
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="text-xs">
                              <b>計費總量</b> = SUM(usage) WHERE category IN filter
                              （= 租戶看到的「本月已用」）
                            </p>
                            <p className="text-xs mt-1">
                              <b>審計總量</b> = SUM(usage) 全部（含 platform 吸收）
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </span>
                    </TableHead>
                    <TableHead>
                      <span className="inline-flex items-center gap-1">
                        平台吸收
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="text-xs">
                              <b>平台吸收</b> = 審計 - 計費 = 不計入租戶額度的用量
                            </p>
                            <p className="text-xs mt-1">
                              代表平台吸收的成本（免費送給租戶的 tokens）
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </span>
                    </TableHead>
                    <TableHead>計費類別</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sorted.map((row) => {
                    const usedRatio =
                      row.base_total > 0
                        ? ((row.base_total - row.base_remaining) /
                            row.base_total) *
                          100
                        : 0;
                    return (
                      <TableRow key={row.tenant_id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {row.tenant_name}
                            {!row.has_ledger && (
                              <Badge variant="outline" className="text-xs">
                                未啟用
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{row.plan_name}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <Progress
                              value={Math.min(100, Math.round(usedRatio))}
                              className="h-2"
                            />
                            <span className="text-xs text-muted-foreground">
                              {formatTokens(
                                row.base_total - row.base_remaining,
                              )}{" "}
                              / {formatTokens(row.base_total)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {addonBadge(row.addon_remaining, row.has_ledger)}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col font-mono text-xs leading-tight">
                            <span className="font-semibold text-sm">
                              {row.total_billable_in_cycle.toLocaleString()}
                            </span>
                            <span className="text-muted-foreground">
                              /
                              {" "}
                              {row.total_audit_in_cycle.toLocaleString()}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {row.platform_absorbed_tokens > 0 ? (
                            <Badge
                              variant="outline"
                              className="border-orange-500 text-orange-600"
                            >
                              {formatTokens(row.platform_absorbed_tokens)}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {categoryBadge(row.included_categories)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}

type SummaryCardProps = {
  label: string;
  value: string;
  highlight?: "destructive";
};

function SummaryCard({ label, value, highlight }: SummaryCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className={
            highlight === "destructive"
              ? "text-2xl font-bold text-destructive"
              : "text-2xl font-bold"
          }
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
