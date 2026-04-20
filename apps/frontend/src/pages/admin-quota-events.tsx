import { useState } from "react";
import type { Variants } from "framer-motion";
import { motion } from "framer-motion";
import { Wallet, AlertTriangle, AlertOctagon } from "lucide-react";
import { formatDateTime } from "@/lib/format-date";
import { useQuotaEvents } from "@/hooks/queries/use-quota-events";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PAGE_SIZE = 20;

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

type EventTypeMeta = {
  label: string;
  badgeClass: string;
  Icon: React.ComponentType<{ className?: string }>;
};

const EVENT_TYPE_META: Record<string, EventTypeMeta> = {
  auto_topup: {
    label: "自動續約",
    badgeClass: "bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/20",
    Icon: Wallet,
  },
  base_warning_80: {
    label: "80% 警示",
    badgeClass: "bg-orange-500/15 text-orange-700 hover:bg-orange-500/20",
    Icon: AlertTriangle,
  },
  base_exhausted_100: {
    label: "額度耗盡",
    badgeClass: "bg-destructive/15 text-destructive hover:bg-destructive/20",
    Icon: AlertOctagon,
  },
};

function formatTokens(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatRatio(ratio: string | null): string {
  if (ratio === null) return "—";
  const n = Number(ratio);
  if (Number.isNaN(n)) return ratio;
  return `${(n * 100).toFixed(1)}%`;
}

function formatAmount(value: string | null, currency: string | null): string {
  if (value === null) return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  const formatted = n.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return currency ? `${currency} ${formatted}` : formatted;
}

export default function AdminQuotaEventsPage() {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, refetch } = useQuotaEvents({
    tenantId,
    page,
    pageSize: PAGE_SIZE,
  });

  const events = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 0;

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
          <h1 className="text-2xl font-bold tracking-tight">額度事件</h1>
          <p className="text-muted-foreground">
            自動續約交易 + 額度警示時間軸（系統管理員專用）
          </p>
        </div>
        <div className="flex items-center gap-3">
          <AdminTenantFilter
            value={tenantId}
            onChange={(v) => {
              setTenantId(v);
              setPage(1);
            }}
          />
          <Button variant="outline" onClick={() => refetch()}>
            重新整理
          </Button>
        </div>
      </motion.div>

      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>事件列表（共 {total} 筆）</CardTitle>
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
            ) : events.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                目前無事件
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-44">時間</TableHead>
                    <TableHead>租戶</TableHead>
                    <TableHead className="w-36">類型</TableHead>
                    <TableHead>內容</TableHead>
                    <TableHead className="w-32 text-right">金額</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => {
                    const meta = EVENT_TYPE_META[event.event_type] ?? {
                      label: event.event_type,
                      badgeClass: "",
                      Icon: AlertTriangle,
                    };
                    return (
                      <TableRow key={event.event_id}>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDateTime(event.created_at)}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-medium">
                              {event.tenant_name || "—"}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {event.cycle_year_month}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className={meta.badgeClass}>
                            <meta.Icon className="mr-1 h-3 w-3" />
                            {meta.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {event.event_type === "auto_topup" ? (
                            <span>
                              續約 +
                              {event.addon_tokens_added != null
                                ? formatTokens(event.addon_tokens_added)
                                : "—"}{" "}
                              tokens
                              {event.reason && (
                                <span className="ml-2 text-xs text-muted-foreground">
                                  ({event.reason})
                                </span>
                              )}
                            </span>
                          ) : (
                            <span className="inline-flex flex-wrap items-center gap-2">
                              <span>{event.message ?? "—"}</span>
                              {event.used_ratio && (
                                <span className="text-xs text-muted-foreground">
                                  使用率 {formatRatio(event.used_ratio)}
                                </span>
                              )}
                              {event.delivered_to_email === true ? (
                                <Badge
                                  variant="outline"
                                  className="border-emerald-500 text-emerald-700 text-xs"
                                >
                                  ✉ 已寄信
                                </Badge>
                              ) : event.delivered_to_email === false ? (
                                <Badge
                                  variant="outline"
                                  className="text-muted-foreground text-xs"
                                >
                                  ⏳ 未寄
                                </Badge>
                              ) : null}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {event.event_type === "auto_topup"
                            ? formatAmount(event.amount_value, event.amount_currency)
                            : "—"}
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

      {totalPages > 1 && (
        <motion.div
          variants={itemVariants}
          className="flex items-center justify-end gap-2"
        >
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一頁
          </Button>
          <span className="text-sm text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            下一頁
          </Button>
        </motion.div>
      )}
    </motion.div>
  );
}
