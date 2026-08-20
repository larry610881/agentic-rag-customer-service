/** Issue #54 §4.5 — Gate run 逐題報告：verdict 燈號 + 每題展開（回應 + 斷言 + trace DAG） */

import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import { AgentTraceGraph } from "@/features/admin/components/agent-trace-graph";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { ExecutionNode } from "@/types/agent-trace";
import type {
  GateRun,
  GateRunCase,
  GateRunDetails,
  GateRunRound,
} from "@/types/config-version";

import { ReplayCompareReport } from "./replay-compare-report";

const FAIL_REASON_LABEL: Record<string, string> = {
  hard_gate: "硬閘門未過（資安/行為不變量）",
  soft_gate: "軟閘門低於門檻",
  budget_exceeded: "超出驗證預算",
};

function VerdictBanner({ run }: { run: GateRun }) {
  if (run.status === "error") {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
        驗證執行失敗：{run.error_message ?? "未知錯誤"}
      </div>
    );
  }
  if (run.status !== "completed") {
    return (
      <div className="flex items-center gap-2 rounded-md border p-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        驗證執行中（{run.status === "queued" ? "排隊中" : "跑題集中"}）…
      </div>
    );
  }
  const passed = run.verdict === "pass";
  return (
    <div
      className={
        passed
          ? "rounded-md border border-green-600/40 bg-green-500/10 p-3 text-sm"
          : "rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm"
      }
    >
      <div className="font-medium">
        {passed ? "✓ 驗證通過" : "✗ 驗證未通過"}
        <span className="ml-2 text-muted-foreground font-normal">
          硬失敗 {run.hard_failed_cases ?? 0} 題 · 軟通過率{" "}
          {run.soft_pass_rate != null
            ? `${(run.soft_pass_rate * 100).toFixed(1)}%`
            : "—"}
          （門檻 {(run.soft_threshold * 100).toFixed(0)}%）· 實際成本 $
          {run.actual_cost?.toFixed(4) ?? "—"} / 預估 $
          {run.est_cost?.toFixed(4) ?? "—"}
        </span>
      </div>
      {!passed && run.fail_reasons.length > 0 && (
        <ul className="mt-1 list-inside list-disc text-destructive">
          {run.fail_reasons.map((r) => (
            <li key={r}>{FAIL_REASON_LABEL[r] ?? r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RoundBlock({ round }: { round: GateRunRound }) {
  const [showTrace, setShowTrace] = useState(false);
  return (
    <div className="rounded-md border p-3 text-sm">
      <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
        <span>第 {round.round + 1} 輪</span>
        <span>{round.latency_ms}ms</span>
        <span>{round.tokens} tokens</span>
        <span>${round.cost.toFixed(5)}</span>
        {round.truncated && <Badge variant="outline">已截斷</Badge>}
      </div>
      <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-muted/50 p-2 text-xs">
        {round.response_text || "（空回應）"}
      </pre>
      <div className="mt-2 flex flex-wrap gap-1">
        {round.assertions.map((a, i) => (
          <Badge
            key={`${a.type}-${i}`}
            variant="outline"
            className={
              a.passed
                ? "border-green-600/50 text-green-700 dark:text-green-400"
                : a.severity === "hard"
                  ? "border-destructive bg-destructive/10 text-destructive"
                  : "border-amber-500/60 text-amber-700 dark:text-amber-400"
            }
            title={a.message}
          >
            {a.passed ? "✓" : "✗"} {a.type}
            {a.severity === "hard" ? "（硬）" : ""}
          </Badge>
        ))}
      </div>
      {round.trace_nodes && round.trace_nodes.length > 0 && (
        <div className="mt-2">
          <button
            type="button"
            className="text-xs text-primary underline-offset-2 hover:underline"
            onClick={() => setShowTrace((v) => !v)}
          >
            {showTrace ? "收合執行軌跡" : "展開執行軌跡 DAG"}
          </button>
          {showTrace && (
            <div className="mt-2 h-64 rounded-md border">
              <AgentTraceGraph
                execNodes={round.trace_nodes as unknown as ExecutionNode[]}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CaseRow({ caseData }: { caseData: GateRunCase }) {
  const [open, setOpen] = useState(false);
  const statusBadge = caseData.hard_failed ? (
    <Badge className="bg-destructive text-destructive-foreground">硬失敗</Badge>
  ) : caseData.soft_passed === false ? (
    <Badge variant="outline" className="border-amber-500 text-amber-600">
      軟未過
    </Badge>
  ) : caseData.unstable ? (
    <Badge variant="outline" className="border-amber-500 text-amber-600">
      通過（不穩定）
    </Badge>
  ) : (
    <Badge variant="outline" className="border-green-600/50 text-green-700 dark:text-green-400">
      通過
    </Badge>
  );

  return (
    <div className="rounded-md border">
      <button
        type="button"
        className="flex w-full items-center gap-2 p-3 text-left text-sm hover:bg-muted/50"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? (
          <ChevronDown className="h-4 w-4 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0" />
        )}
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {caseData.priority}
        </Badge>
        <span className="min-w-0 flex-1 truncate">{caseData.question}</span>
        {caseData.pass_rate != null && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {(caseData.pass_rate * 100).toFixed(0)}%
          </span>
        )}
        {statusBadge}
      </button>
      {open && (
        <div className="space-y-2 border-t p-3">
          {caseData.rounds.map((r) => (
            <RoundBlock key={r.round} round={r} />
          ))}
        </div>
      )}
    </div>
  );
}

export function GateRunReport({ run }: { run: GateRun }) {
  // Phase G — 回放對比復用 gate run 容器，依 details.type 分流
  if (run.details?.type === "replay_compare") {
    return <ReplayCompareReport run={run} />;
  }
  const details = run.details as GateRunDetails | null;
  const cases = details?.cases ?? [];
  const excluded = details?.excluded_platform_cases ?? [];
  return (
    <Card className="space-y-3 p-4">
      <VerdictBanner run={run} />
      {details?.aborted && (
        <p className="text-xs text-destructive">
          ⚠ 驗證因超出預算而提前中止，以下為中止前的結果。
        </p>
      )}
      {cases.length > 0 && (
        <div className="space-y-2">
          {cases.map((c) => (
            <CaseRow key={c.case_id} caseData={c} />
          ))}
        </div>
      )}
      {excluded.length > 0 && (
        <p className="text-xs text-muted-foreground">
          本次依 bot 設定排除了 {excluded.length} 題平台通用題（審計紀錄已保留）。
        </p>
      )}
    </Card>
  );
}
