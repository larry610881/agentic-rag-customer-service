/** Issue #54 Phase E — 版本時間線頁：設定版本 × 閘門 × 服役數據 */

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronDown,
  ChevronRight,
  GitBranch,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BotConfigTimeline } from "@/features/admin/components/bot-config-timeline";
import { GateRunReport } from "@/features/admin/components/prompt-optimizer/gate-run-report";
import { PromptDiff } from "@/features/admin/components/prompt-optimizer/prompt-diff";
import { VersionMetricsCard } from "@/features/admin/components/prompt-optimizer/version-metrics-card";
import { useBots } from "@/hooks/queries/use-bots";
import {
  useConfigVersion,
  useConfigVersions,
  useGateEstimate,
  useGateRun,
  useInvalidateVersionsOnGateComplete,
  usePublishConfigVersion,
  useRejectConfigVersion,
  useReplayCompare,
  useRollbackConfigVersion,
  useValidateConfigVersion,
} from "@/hooks/queries/use-config-versions";
import type { ConfigVersion } from "@/types/config-version";

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  validating: "驗證中",
  pending_publish: "待發布",
  published: "已發布",
  rejected: "已放棄",
};

const SOURCE_LABEL: Record<string, string> = {
  manual: "手動編輯",
  optimizer: "自動優化",
  rollback: "回滾",
  seed: "初始",
};

const VERDICT_LABEL: Record<string, string> = {
  pass: "通過",
  fail: "未通過",
  forced: "強制發布",
  skipped: "未驗證",
};

function statusBadgeClass(status: string): string {
  switch (status) {
    case "published":
      return "border-green-600/50 text-green-700 dark:text-green-400";
    case "pending_publish":
      return "border-blue-500/60 text-blue-600 dark:text-blue-400";
    case "validating":
      return "border-amber-500/60 text-amber-600 dark:text-amber-400";
    case "rejected":
      return "border-muted-foreground/40 text-muted-foreground";
    default:
      return "";
  }
}

function errorMessage(err: unknown): string {
  return err instanceof Error && err.message ? err.message : "操作失敗";
}

interface VersionCardProps {
  botId: string;
  version: ConfigVersion;
  currentBasePrompt: string;
  gateMode: "off" | "warn" | "block";
}

function VersionCard({
  botId,
  version,
  currentBasePrompt,
  gateMode,
}: VersionCardProps) {
  const [open, setOpen] = useState(false);
  const [estimateOpen, setEstimateOpen] = useState(false);
  const { data: detail } = useConfigVersion(
    botId,
    open ? version.id : "",
  );
  // 驗證中 / 已驗證：抓 gate run（validating 時 3s polling）
  const { data: gateRun } = useGateRun(open ? version.gate_run_id : null);
  // H18：gate run 完成 → 刷新版本列表，讓卡片脫離 stale 的 "validating"
  useInvalidateVersionsOnGateComplete(botId, gateRun?.status);
  const { data: estimate, isLoading: estimateLoading } = useGateEstimate(
    botId,
    estimateOpen,
  );

  const publishMutation = usePublishConfigVersion();
  const rejectMutation = useRejectConfigVersion();
  const rollbackMutation = useRollbackConfigVersion();
  const validateMutation = useValidateConfigVersion();
  const replayMutation = useReplayCompare();
  const [replayRunId, setReplayRunId] = useState<string | null>(null);
  const { data: replayRun } = useGateRun(replayRunId);

  const busy =
    publishMutation.isPending ||
    rejectMutation.isPending ||
    rollbackMutation.isPending ||
    validateMutation.isPending ||
    replayMutation.isPending;

  const handlePublish = (force = false) => {
    publishMutation.mutate(
      { botId, versionId: version.id, force },
      {
        onSuccess: () =>
          toast.success(
            force ? "已強制發布（記錄為 forced）" : "版本已發布上線",
          ),
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  };

  const handleValidate = () => {
    validateMutation.mutate(
      { botId, versionId: version.id },
      {
        onSuccess: () => {
          setEstimateOpen(false);
          setOpen(true);
          toast.success("驗證已啟動，結果將自動更新");
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  };

  const snapshotPrompt =
    (detail?.config_snapshot?.base_prompt as string | undefined) ?? "";
  const gateOn = gateMode !== "off";
  const canForce =
    gateMode === "warn" &&
    version.status === "draft" &&
    version.gate_verdict === "fail";

  return (
    <Card className="p-4">
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? (
          <ChevronDown className="h-4 w-4 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0" />
        )}
        <span className="font-semibold">v{version.version_no}</span>
        {version.is_current && (
          <Badge className="bg-green-600 text-white">線上</Badge>
        )}
        <Badge variant="outline" className={statusBadgeClass(version.status)}>
          {STATUS_LABEL[version.status] ?? version.status}
        </Badge>
        <Badge variant="outline" className="text-[10px]">
          {SOURCE_LABEL[version.source] ?? version.source}
        </Badge>
        {version.gate_verdict && (
          <Badge
            variant="outline"
            className={
              version.gate_verdict === "fail"
                ? "border-destructive text-destructive"
                : "text-[10px]"
            }
          >
            閘門：{VERDICT_LABEL[version.gate_verdict] ?? version.gate_verdict}
          </Badge>
        )}
        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
          {version.changed_fields.join("、")}
        </span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {new Date(version.created_at).toLocaleString()}
        </span>
      </button>

      {/* 操作列 */}
      <div className="mt-3 flex flex-wrap gap-2">
        {version.status === "draft" && gateOn && (
          <>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setEstimateOpen(true)}
            >
              <ShieldCheck className="mr-1 h-4 w-4" />
              送驗
            </Button>
            {canForce && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button size="sm" variant="outline" disabled={busy}>
                    強制發布
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>強制發布？</AlertDialogTitle>
                    <AlertDialogDescription>
                      此版本閘門驗證未通過（warn 模式）。強制發布會上線並永久記錄為
                      forced。
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>取消</AlertDialogCancel>
                    <AlertDialogAction onClick={() => handlePublish(true)}>
                      確認強制發布
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </>
        )}
        {version.status === "draft" && !gateOn && (
          <Button size="sm" disabled={busy} onClick={() => handlePublish()}>
            發布
          </Button>
        )}
        {version.status === "pending_publish" && (
          <Button size="sm" disabled={busy} onClick={() => handlePublish()}>
            發布上線
          </Button>
        )}
        {(version.status === "draft" ||
          version.status === "pending_publish") && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() =>
              rejectMutation.mutate(
                { botId, versionId: version.id },
                {
                  onSuccess: () => toast.success("已放棄此版本"),
                  onError: (err) => toast.error(errorMessage(err)),
                },
              )
            }
          >
            放棄
          </Button>
        )}
        {version.status === "published" && !version.is_current && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" variant="outline" disabled={busy}>
                回滾至此版
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>回滾到 v{version.version_no}？</AlertDialogTitle>
                <AlertDialogDescription>
                  將以此版快照建立新版本並直接上線（免重驗；設定採 overlay
                  合併，憑證與外觀不受影響）。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() =>
                    rollbackMutation.mutate(
                      { botId, targetVersionId: version.id },
                      {
                        onSuccess: () => toast.success("已回滾並上線"),
                        onError: (err) => toast.error(errorMessage(err)),
                      },
                    )
                  }
                >
                  確認回滾
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
        {version.status !== "validating" && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" variant="ghost" disabled={busy}>
                回放對比
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>真實流量回放對比</AlertDialogTitle>
                <AlertDialogDescription>
                  抽此 bot 最近 10 則真實使用者問題，「線上版 vs
                  此版本」各影子執行一次並由 LLM 換位雙判勝負。
                  約 20 次受測呼叫 + 20 次評審呼叫，
                  <span className="font-medium">
                    消耗 token 並計入租戶用量
                  </span>
                  ；與閘門共用每日次數與預算上限。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() =>
                    replayMutation.mutate(
                      { botId, versionId: version.id },
                      {
                        onSuccess: (run) => {
                          setReplayRunId((run as { id: string }).id);
                          setOpen(true);
                          toast.success("回放對比已啟動，結果將自動更新");
                        },
                        onError: (err) => toast.error(errorMessage(err)),
                      },
                    )
                  }
                >
                  確認啟動
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
        {version.status === "validating" && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            驗證中…（展開查看進度）
          </span>
        )}
      </div>

      {/* estimate 確認 dialog */}
      <AlertDialog open={estimateOpen} onOpenChange={setEstimateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>驗證成本預檢</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-1 text-sm">
                {estimateLoading && <Skeleton className="h-16 w-full" />}
                {estimate && (
                  <>
                    <p>
                      題集 {estimate.total_cases} 題（P0 {estimate.p0_cases}{" "}
                      題 × {estimate.repeats} 輪）≈ {estimate.est_calls} 次呼叫
                    </p>
                    <p>
                      預估成本{" "}
                      <span className="font-medium">
                        ${estimate.est_cost.toFixed(4)}
                      </span>
                      （預算上限 ${estimate.budget_usd}）
                      {!estimate.within_budget && (
                        <span className="text-destructive">
                          {" "}
                          — 超出預算，將被拒絕
                        </span>
                      )}
                    </p>
                    {estimate.excluded_platform_cases.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        已依設定排除 {estimate.excluded_platform_cases.length}{" "}
                        題平台通用題。
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      此驗證消耗 token 並計入租戶用量（分類：閘門驗證）。
                    </p>
                  </>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              // L17：estimate 載入完成前不可送驗——預檢確認的知情同意（題數/
              // 成本/預算）必須先看到才可按；超預算亦禁用（後端同樣會擋）
              disabled={
                validateMutation.isPending ||
                estimateLoading ||
                !estimate ||
                !estimate.within_budget
              }
              onClick={handleValidate}
            >
              確認送驗
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 展開區：diff + gate run 報告 + 成效卡 */}
      {open && (
        <div className="mt-4 space-y-3 border-t pt-3">
          {detail ? (
            <PromptDiff
              before={currentBasePrompt}
              after={snapshotPrompt}
              title={`base_prompt：線上 vs v${version.version_no}`}
            />
          ) : (
            <Skeleton className="h-24 w-full" />
          )}
          {gateRun && <GateRunReport run={gateRun} />}
          {replayRun && <GateRunReport run={replayRun} />}
          {version.status === "published" && (
            <VersionMetricsCard botId={botId} versionId={version.id} />
          )}
        </div>
      )}
    </Card>
  );
}

export default function AdminPromptOptimizerVersionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const botId = searchParams.get("botId") ?? "";
  const { data: botsData } = useBots(1, 100);
  const bots = botsData?.items ?? [];
  const selectedBot = bots.find((b) => b.id === botId);

  const { data, isLoading } = useConfigVersions(botId, 1, 50);
  const versions = data?.items ?? [];

  const currentVersion = versions.find((v) => v.is_current);
  const { data: currentDetail } = useConfigVersion(
    botId,
    currentVersion?.id ?? "",
  );
  const currentBasePrompt = useMemo(
    () =>
      (currentDetail?.config_snapshot?.base_prompt as string | undefined) ??
      "",
    [currentDetail],
  );

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center gap-3">
        <GitBranch className="h-5 w-5" />
        <h1 className="text-xl font-semibold">版本與發布</h1>
        <div className="ml-auto w-64">
          <Select
            value={botId}
            onValueChange={(v) => setSearchParams({ botId: v })}
          >
            <SelectTrigger>
              <SelectValue placeholder="選擇機器人" />
            </SelectTrigger>
            <SelectContent>
              {bots.map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {!botId && (
        <p className="text-sm text-muted-foreground">
          選擇一個機器人以查看其設定版本歷史。
        </p>
      )}

      {botId && selectedBot && (
        <p className="text-xs text-muted-foreground">
          閘門模式：
          <Badge variant="outline" className="ml-1">
            {selectedBot.gate_mode}
          </Badge>
          {selectedBot.gate_mode !== "off" &&
            ` · 軟門檻 ${(selectedBot.gate_soft_threshold * 100).toFixed(0)}% · P0 重跑 ${selectedBot.gate_repeats} 輪 · 預算 $${selectedBot.gate_budget_usd}`}
        </p>
      )}

      {botId && (
        <Tabs defaultValue="versions">
          <TabsList>
            <TabsTrigger value="versions">設定版本</TabsTrigger>
            {/* Issue #60：對話實際生效的設定 hash 時間軸（與版本表獨立，可對照 drift） */}
            <TabsTrigger value="timeline">生效設定時間軸</TabsTrigger>
          </TabsList>
          <TabsContent value="versions" className="space-y-3 pt-3">
            {isLoading && <Skeleton className="h-40 w-full" />}
            {!isLoading && versions.length === 0 && (
              <p className="text-sm text-muted-foreground">
                尚無版本紀錄——首次修改設定時會自動建立。
              </p>
            )}
            {versions.map((v) => (
              <VersionCard
                key={v.id}
                botId={botId}
                version={v}
                currentBasePrompt={currentBasePrompt}
                gateMode={selectedBot?.gate_mode ?? "off"}
              />
            ))}
          </TabsContent>
          <TabsContent value="timeline" className="pt-3">
            <BotConfigTimeline botId={botId} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
