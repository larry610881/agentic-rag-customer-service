/** Phase G — 真實流量回放 pairwise 對比報告：勝負統計 + 逐題並排回應 */

import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type {
  GateRun,
  ReplayCompareDetails,
  ReplayCompareItem,
} from "@/types/config-version";

const VERDICT_BADGE: Record<
  ReplayCompareItem["verdict"],
  { label: string; className: string }
> = {
  candidate: {
    label: "草稿勝",
    className: "border-green-600/50 text-green-700 dark:text-green-400",
  },
  baseline: {
    label: "線上勝",
    className: "border-blue-500/60 text-blue-600 dark:text-blue-400",
  },
  tie: { label: "平手", className: "text-muted-foreground" },
};

function ReplayItemRow({ item }: { item: ReplayCompareItem }) {
  const [open, setOpen] = useState(false);
  const badge = VERDICT_BADGE[item.verdict];
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
        <span className="min-w-0 flex-1 truncate">{item.question}</span>
        <Badge variant="outline" className={badge.className}>
          {badge.label}
        </Badge>
      </button>
      {open && (
        <div className="grid gap-2 border-t p-3 md:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              線上版（${item.baseline_cost.toFixed(5)}）
            </p>
            <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-muted/50 p-2 text-xs">
              {item.baseline_answer || "（空回應）"}
            </pre>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              草稿版（${item.candidate_cost.toFixed(5)}）
            </p>
            <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-muted/50 p-2 text-xs">
              {item.candidate_answer || "（空回應）"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export function ReplayCompareReport({ run }: { run: GateRun }) {
  const details = run.details as ReplayCompareDetails | null;

  if (run.status === "error") {
    return (
      <Card className="p-4 text-sm text-destructive">
        回放對比失敗：{run.error_message ?? "未知錯誤"}
      </Card>
    );
  }
  if (run.status !== "completed") {
    return (
      <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        回放對比執行中（{run.total_cases ?? "?"} 題 × 2 版 + 換位雙判）…
      </Card>
    );
  }

  const summary = details?.summary;
  const items = details?.items ?? [];
  return (
    <Card className="space-y-3 p-4">
      {summary && (
        <div className="rounded-md border p-3 text-sm">
          <span className="font-medium">
            回放對比：草稿 {summary.candidate_wins} 勝 · 線上{" "}
            {summary.baseline_wins} 勝 · {summary.ties} 平
          </span>
          <span className="ml-2 text-muted-foreground">
            （草稿勝率 {(summary.win_rate * 100).toFixed(0)}%；判定經換位雙判，
            不一致計平手；實際成本 ${run.actual_cost?.toFixed(4) ?? "—"}）
          </span>
        </div>
      )}
      {details?.aborted && (
        <p className="text-xs text-destructive">
          ⚠ 因超出預算提前中止，以下為部分結果。
        </p>
      )}
      <div className="space-y-2">
        {items.map((item, i) => (
          <ReplayItemRow key={`${i}-${item.question.slice(0, 20)}`} item={item} />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        樣本為此 bot 最近的真實使用者問題；LLM 對比判定僅供發布決策參考。
      </p>
    </Card>
  );
}
