import type { Variants } from "framer-motion";
import { motion } from "framer-motion";
import { Wallet } from "lucide-react";
import { useAuthStore } from "@/stores/use-auth-store";
import { useTenantQuota } from "@/hooks/queries/use-tenant-quota";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { getCategoryLabel } from "@/constants/usage-categories";

const containerVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
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
  return n.toLocaleString();
}

export default function QuotaPage() {
  const tenantId = useAuthStore((s) => s.tenantId);
  const { data, isLoading, isError } = useTenantQuota(tenantId);

  const baseUsedPct =
    data && data.base_total > 0
      ? ((data.base_total - data.base_remaining) / data.base_total) * 100
      : 0;
  const baseAlert = baseUsedPct >= 80;

  return (
    <motion.div
      className="flex flex-col gap-6 p-6"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={itemVariants}>
        <h1 className="text-2xl font-bold tracking-tight">本月額度</h1>
        <p className="text-muted-foreground">
          {data ? `${data.cycle_year_month} 用量與餘額` : "載入中…"}
        </p>
      </motion.div>

      {!tenantId ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            尚未綁定租戶
          </CardContent>
        </Card>
      ) : isError ? (
        <Card>
          <CardContent className="py-12 text-center text-destructive">
            載入失敗，請稍後再試
          </CardContent>
        </Card>
      ) : isLoading || !data ? (
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : (
        <>
          <motion.div
            variants={itemVariants}
            className="grid gap-4 md:grid-cols-3"
          >
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>{data.cycle_year_month}</CardDescription>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  本月已用
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {formatTokens(data.total_used_in_cycle)}
                </div>
                <p className="text-xs text-muted-foreground">tokens</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Base 餘額（{data.plan_name}）
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Progress
                  value={Math.min(100, Math.round(baseUsedPct))}
                  className="h-2"
                />
                <div
                  className={
                    baseAlert
                      ? "text-sm font-medium text-orange-600"
                      : "text-sm text-muted-foreground"
                  }
                >
                  {formatTokens(data.base_remaining)} /{" "}
                  {formatTokens(data.base_total)}
                </div>
                {baseAlert && (
                  <p className="text-xs text-orange-600">
                    Base 額度已使用 {Math.round(baseUsedPct)}%，請留意
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Addon 餘額
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div
                  className={
                    data.addon_remaining < 0
                      ? "text-3xl font-bold text-destructive"
                      : "text-3xl font-bold"
                  }
                >
                  {data.addon_remaining > 0 ? "+" : ""}
                  {formatTokens(data.addon_remaining)}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  POC 階段超用會持續累積，月初將自動補 10M（規劃中）
                </p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={itemVariants}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Wallet className="h-4 w-4" />
                  計費類別
                </CardTitle>
                <CardDescription>
                  使用以下類別時會扣除本月額度（系統管理員可調整）
                </CardDescription>
              </CardHeader>
              <CardContent>
                {data.included_categories === null ? (
                  <Badge variant="secondary">全部計入</Badge>
                ) : data.included_categories.length === 0 ? (
                  <Badge
                    variant="outline"
                    className="border-orange-500 text-orange-600"
                  >
                    全部不計入（不扣帳）
                  </Badge>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {data.included_categories.map((c) => (
                      <Badge key={c} variant="outline">
                        {getCategoryLabel(c)}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </>
      )}
    </motion.div>
  );
}
