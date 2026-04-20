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

const USAGE_CATEGORY_LABEL: Record<string, string> = {
  rag: "RAG",
  chat_web: "Web",
  chat_widget: "Widget",
  chat_line: "LINE",
  ocr: "OCR",
  embedding: "Embedding",
  guard: "Guard",
  rerank: "Rerank",
  contextual_retrieval: "Contextual",
  pdf_rename: "PDF Rename",
  auto_classification: "Auto Class.",
  intent_classify: "Intent",
  other: "Other",
};

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
          {USAGE_CATEGORY_LABEL[c] ?? c}
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
      (a, b) => b.total_used_in_cycle - a.total_used_in_cycle,
    );
  }, [data]);

  const summary = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        tenantCount: 0,
        activeLedgers: 0,
        baseUsedPct: 0,
        addonTotal: 0,
      };
    }
    let activeLedgers = 0;
    let baseUsedSum = 0;
    let baseTotalSum = 0;
    let addonTotal = 0;
    for (const item of data) {
      if (item.has_ledger) activeLedgers += 1;
      baseUsedSum += item.base_total - item.base_remaining;
      baseTotalSum += item.base_total;
      addonTotal += item.addon_remaining;
    }
    const baseUsedPct =
      baseTotalSum > 0 ? Math.round((baseUsedSum / baseTotalSum) * 100) : 0;
    return {
      tenantCount: data.length,
      activeLedgers,
      baseUsedPct,
      addonTotal,
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
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
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
                    <TableHead className="min-w-[220px]">Base 進度</TableHead>
                    <TableHead>Addon 餘額</TableHead>
                    <TableHead>本月已用</TableHead>
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
                          <span className="font-mono">
                            {row.total_used_in_cycle.toLocaleString()}
                          </span>
                          <span className="ml-1 text-xs text-muted-foreground">
                            tokens
                          </span>
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
