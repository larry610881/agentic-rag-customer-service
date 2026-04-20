import { useEffect, useRef } from "react";
import {
  Brain,
  Wrench,
  BookOpen,
  UserRound,
  Route,
  Hash,
  MessageSquare,
  CheckCircle2,
  AlertTriangle,
  Activity,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { SSEEvent } from "@/lib/sse-client";

type TimelineCardSpec = {
  type: string;
  icon: LucideIcon;
  label: string;
  detail: string;
  tsMs: number;
  tone: "default" | "success" | "warn" | "info";
};

const TYPE_LABELS: Record<string, string> = {
  status: "狀態",
  tool_calls: "工具呼叫",
  sources: "知識庫召回",
  contact: "聯絡資訊",
  worker_routing: "路由決策",
  message_id: "訊息 ID",
  conversation_id: "對話 ID",
  done: "完成",
  error: "錯誤",
};

const TYPE_ICONS: Record<string, LucideIcon> = {
  status: Brain,
  tool_calls: Wrench,
  sources: BookOpen,
  contact: UserRound,
  worker_routing: Route,
  message_id: Hash,
  conversation_id: MessageSquare,
  done: CheckCircle2,
  error: AlertTriangle,
};

function eventToCard(event: SSEEvent): TimelineCardSpec | null {
  if (event.type === "token") return null;
  const tsMs =
    typeof event.ts_ms === "number" && event.ts_ms > 0 ? event.ts_ms : 0;
  const icon = TYPE_ICONS[event.type] ?? Activity;
  const label = TYPE_LABELS[event.type] ?? event.type;
  let detail = "";
  let tone: TimelineCardSpec["tone"] = "default";

  if (event.type === "status" && typeof event.status === "string") {
    detail = event.status;
    tone = "info";
  } else if (event.type === "tool_calls" && Array.isArray(event.tool_calls)) {
    detail = (event.tool_calls as Array<{ tool_name: string }>)
      .map((c) => c.tool_name)
      .join(", ");
    tone = "info";
  } else if (event.type === "sources" && Array.isArray(event.sources)) {
    detail = `${event.sources.length} chunks`;
    tone = "info";
  } else if (
    event.type === "worker_routing" &&
    typeof event.worker_name === "string"
  ) {
    detail = `→ ${event.worker_name}`;
    tone = "info";
  } else if (event.type === "done" && typeof event.trace_id === "string") {
    detail = `trace=${(event.trace_id as string).slice(0, 8)}`;
    tone = "success";
  } else if (event.type === "error" && typeof event.message === "string") {
    detail = event.message as string;
    tone = "warn";
  }

  return { type: event.type, icon, label, detail, tsMs, tone };
}

const TONE_CLASS_ACTIVE: Record<TimelineCardSpec["tone"], string> = {
  default: "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100",
  info: "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100",
  success: "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100",
  warn: "border-red-500 bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-100",
};

const TONE_CLASS_PAST: Record<TimelineCardSpec["tone"], string> = {
  default: "border-muted bg-background text-muted-foreground",
  info: "border-violet-200 bg-violet-50/40 text-violet-900 dark:border-violet-800 dark:bg-violet-950/30 dark:text-violet-200",
  success: "border-emerald-200 bg-emerald-50/40 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200",
  warn: "border-red-200 bg-red-50/40 text-red-900 dark:border-red-800 dark:bg-red-950/30 dark:text-red-200",
};

export type ExecutionTimelineProps = {
  events: SSEEvent[];
};

/**
 * 水平時序卡片帶狀軸 — 取代既有直立 ExecutionFeed。
 * 工具/事件多時，最新一張卡會自動 scroll 到視窗中央，
 * 讓使用者不用手動捲動就能看到「現在跑到哪」。
 */
export function ExecutionTimeline({ events }: ExecutionTimelineProps) {
  const cards = events
    .map(eventToCard)
    .filter((c): c is TimelineCardSpec => c !== null);
  const activeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = activeRef.current;
    if (!el) return;
    el.scrollIntoView({
      inline: "center",
      block: "nearest",
      behavior: "smooth",
    });
  }, [cards.length]);

  return (
    <Card className="p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium">
        <Activity className="h-4 w-4 text-emerald-500" />
        執行時序
        <span className="text-xs font-normal text-muted-foreground">
          每筆事件由左→右排列，最新自動置中
        </span>
      </div>
      {cards.length === 0 ? (
        <div className="flex h-[78px] items-center justify-center text-xs text-muted-foreground">
          對話開始後事件會由左至右展開
        </div>
      ) : (
        <div className="flex snap-x snap-mandatory items-stretch gap-2 overflow-x-auto pb-1">
          {cards.map((card, idx) => {
            const isActive = idx === cards.length - 1;
            const Icon = card.icon;
            return (
              <div
                key={`${card.type}-${idx}-${card.tsMs}`}
                ref={isActive ? activeRef : undefined}
                className={cn(
                  "flex min-w-[140px] max-w-[220px] shrink-0 snap-center flex-col gap-1 rounded-md border p-2 transition-all duration-200",
                  isActive
                    ? `${TONE_CLASS_ACTIVE[card.tone]} shadow scale-[1.04]`
                    : `${TONE_CLASS_PAST[card.tone]} opacity-80`,
                )}
              >
                <div className="flex items-center gap-1.5 text-xs font-medium">
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{card.label}</span>
                  {card.tsMs > 0 && (
                    <span className="ml-auto rounded bg-background/60 px-1 font-mono text-[10px]">
                      {card.tsMs.toFixed(0)}ms
                    </span>
                  )}
                </div>
                {card.detail && (
                  <div className="truncate text-[11px]">{card.detail}</div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
