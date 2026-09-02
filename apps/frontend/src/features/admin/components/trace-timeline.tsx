import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ExecutionNode } from "@/types/agent-trace";
import {
  NODE_COLORS_FAILED,
  durationColor,
  nodeColorClass,
} from "@/features/admin/lib/trace-node-style";
import { cn } from "@/lib/utils";
import {
  buildTraceTimeline,
  type TimelineRow,
  type TimelineSegment,
} from "./trace-timeline-layout";

/**
 * Issue #57 — trace 時間軸（waterfall / Gantt）視圖。
 *
 * 純 CSS 定位（left% / width%），配色沿用 DAG 的 node_type → NODE_COLORS 對照表，
 * 未知類型退回灰色。父列預設收合、以直接子節點的連續色塊 inline 顯示；
 * 子節點時間重疊時自動展開成子列，避免色塊互相蓋住。
 */

// 與 DAG 一樣：本專案 admin 元件字串直接寫 zh-TW，未使用 i18n runtime。
const T = {
  timeline: "時間軸",
  node: "節點",
  duration: "耗時",
  percent: "占比",
  gap: "其他（未儀表化）",
  criticalPath: "關鍵路徑",
  totalWall: "總耗時",
  empty: "沒有時間資料",
  expand: "展開",
  collapse: "收合",
} as const;

/** 固定列高（對應 Tailwind h-8） */
export const TIMELINE_ROW_HEIGHT_PX = 32;

/**
 * 預設展開規則：root 一律展開（否則整張時間軸只剩一列）；
 * 其他父列收合、以 inline segment 呈現，除非子節點時間重疊會互相蓋住。
 */
function defaultExpanded(row: TimelineRow): boolean {
  return row.isRoot || row.childrenOverlap;
}

// 斜紋以 theme token 著色（color-mix 取 muted-foreground 20%），light/dark 自動跟隨
const GAP_CLASS =
  "border-dashed border-muted-foreground/40 bg-muted/70 dark:bg-muted/40 " +
  "[background-image:repeating-linear-gradient(135deg,transparent_0_4px,color-mix(in_oklch,var(--color-muted-foreground)_20%,transparent)_4px_6px)]";

function fmtMs(ms: number): string {
  return `${ms.toFixed(0)}ms`;
}

function fmtPct(pct: number): string {
  return `${pct.toFixed(pct >= 10 ? 0 : 1)}%`;
}

function segmentTitle(s: TimelineSegment): string {
  const label = s.isGap ? T.gap : s.label;
  return `${label} · ${fmtMs(s.durationMs)} (${fmtPct(s.percentOfWall)})`;
}

function colorFor(nodeType: string, outcome?: ExecutionNode["outcome"]): string {
  if (outcome === "failed") return NODE_COLORS_FAILED;
  return nodeColorClass(nodeType);
}

type BarProps = {
  seg: TimelineSegment;
  colorClass: string;
  emphasised: boolean;
  onClick?: () => void;
  testId?: string;
};

function Bar({ seg, colorClass, emphasised, onClick, testId }: BarProps) {
  // 極短節點至少留 2px 讓使用者看得到；0 時長仍顯示細線
  const style = {
    left: `${seg.leftPct}%`,
    width: `${seg.widthPct}%`,
    minWidth: seg.isGap ? undefined : 2,
  };
  const common = cn(
    "absolute top-1 bottom-1 rounded-sm border transition-opacity",
    colorClass,
    emphasised ? "border-2 opacity-100" : "opacity-60 hover:opacity-90",
    onClick && "cursor-pointer",
  );
  if (!onClick) {
    return (
      <div
        data-testid={testId}
        className={common}
        style={style}
        title={segmentTitle(seg)}
        aria-label={segmentTitle(seg)}
      />
    );
  }
  return (
    <button
      type="button"
      data-testid={testId}
      className={common}
      style={style}
      title={segmentTitle(seg)}
      aria-label={segmentTitle(seg)}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    />
  );
}

type TimelineRowViewProps = {
  row: TimelineRow;
  expanded: boolean;
  onToggle: (nodeId: string) => void;
  onSelectNode?: (nodeId: string) => void;
};

function TimelineRowView({
  row,
  expanded,
  onToggle,
  onSelectNode,
}: TimelineRowViewProps) {
  const n = row.node;
  const emphasised = row.isCriticalPath;
  const showInlineSegments =
    row.hasChildren && !expanded && row.segments.length > 0;
  const select = onSelectNode ? () => onSelectNode(row.nodeId) : undefined;
  const ownSeg: TimelineSegment = {
    nodeId: row.nodeId,
    nodeType: n.node_type,
    label: n.label,
    startMs: row.startMs,
    endMs: row.endMs,
    durationMs: row.durationMs,
    leftPct: row.leftPct,
    widthPct: row.widthPct,
    percentOfWall: row.percentOfWall,
    isGap: false,
  };

  return (
    <div
      data-testid={`timeline-row-${row.nodeId}`}
      data-critical={emphasised ? "true" : "false"}
      className={cn(
        "flex h-8 items-center gap-2 border-b border-border/60 text-xs",
        emphasised ? "text-foreground" : "text-muted-foreground",
      )}
    >
      {/* label column */}
      <div
        className="flex w-56 shrink-0 items-center gap-1 overflow-hidden"
        style={{ paddingLeft: 8 + row.depth * 14 }}
      >
        {row.hasChildren ? (
          <button
            type="button"
            aria-label={`${expanded ? T.collapse : T.expand} ${n.label}`}
            aria-expanded={expanded}
            data-testid={`timeline-toggle-${row.nodeId}`}
            className="flex h-4 w-4 shrink-0 items-center justify-center rounded hover:bg-muted"
            onClick={() => onToggle(row.nodeId)}
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        ) : (
          <span className="h-4 w-4 shrink-0" />
        )}
        <span
          className={cn("truncate", emphasised && "font-semibold")}
          title={`${n.label} (${n.node_type})`}
        >
          {n.label}
        </span>
        {n.outcome === "failed" && (
          <span className="shrink-0 rounded bg-red-100 px-1 text-[10px] font-medium text-red-700 dark:bg-red-900 dark:text-red-200">
            FAILED
          </span>
        )}
      </div>

      {/* bar column */}
      <div className="relative h-full min-w-0 flex-1">
        {showInlineSegments ? (
          <>
            {/* 父節點自身範圍：淡底當容器，子色塊疊在上面 */}
            <Bar
              seg={ownSeg}
              colorClass={cn(colorFor(n.node_type, n.outcome), "opacity-30")}
              emphasised={false}
              onClick={select}
              testId={`timeline-bar-${row.nodeId}`}
            />
            {row.gaps.map((g, i) => (
              <Bar
                key={`gap-${i}`}
                seg={g}
                colorClass={GAP_CLASS}
                emphasised={false}
                testId={`timeline-gap-${row.nodeId}-${i}`}
              />
            ))}
            {row.segments.map((s) => (
              <Bar
                key={s.nodeId ?? `${s.startMs}-${s.endMs}`}
                seg={s}
                colorClass={colorFor(s.nodeType)}
                emphasised={emphasised}
                onClick={
                  onSelectNode && s.nodeId
                    ? () => onSelectNode(s.nodeId as string)
                    : undefined
                }
                testId={`timeline-segment-${s.nodeId}`}
              />
            ))}
          </>
        ) : (
          <>
            <Bar
              seg={ownSeg}
              colorClass={colorFor(n.node_type, n.outcome)}
              emphasised={emphasised}
              onClick={select}
              testId={`timeline-bar-${row.nodeId}`}
            />
            {row.gaps.map((g, i) => (
              <Bar
                key={`gap-${i}`}
                seg={g}
                colorClass={GAP_CLASS}
                emphasised={false}
                testId={`timeline-gap-${row.nodeId}-${i}`}
              />
            ))}
          </>
        )}
      </div>

      {/* metrics column */}
      <div className="flex w-32 shrink-0 items-center justify-end gap-2 pr-2 font-mono">
        <span className={durationColor(row.durationMs)}>{fmtMs(row.durationMs)}</span>
        <span
          className="w-12 text-right text-muted-foreground"
          data-testid={`timeline-pct-${row.nodeId}`}
        >
          {fmtPct(row.percentOfWall)}
        </span>
      </div>
    </div>
  );
}

export type TraceTimelineProps = {
  nodes: ExecutionNode[];
  totalMs: number;
  /** 點擊 bar / segment 時回呼對應節點 id */
  onSelectNode?: (nodeId: string) => void;
  className?: string;
};

export function TraceTimeline({
  nodes,
  totalMs,
  onSelectNode,
  className,
}: TraceTimelineProps) {
  const layout = useMemo(() => buildTraceTimeline(nodes, totalMs), [nodes, totalMs]);

  // 使用者手動切換的狀態；未切換過的父列依 defaultExpanded 決定
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const rowById = useMemo(
    () => new Map(layout.rows.map((r) => [r.nodeId, r])),
    [layout],
  );
  const isExpanded = (row: TimelineRow) =>
    toggled[row.nodeId] ?? defaultExpanded(row);
  const onToggle = (nodeId: string) => {
    const row = rowById.get(nodeId);
    if (!row) return;
    setToggled((prev) => ({
      ...prev,
      [nodeId]: !(prev[nodeId] ?? defaultExpanded(row)),
    }));
  };

  const visibleRows = useMemo(() => {
    const out: TimelineRow[] = [];
    for (const row of layout.rows) {
      let visible = true;
      let pid = row.parentId;
      while (pid) {
        const parent = rowById.get(pid);
        if (!parent) break;
        if (!(toggled[pid] ?? defaultExpanded(parent))) {
          visible = false;
          break;
        }
        pid = parent.parentId;
      }
      if (visible) out.push(row);
    }
    return out;
  }, [layout, rowById, toggled]);

  if (layout.rows.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {T.empty}
      </div>
    );
  }

  const showSyntheticWall = layout.rootId === null;

  return (
    <div
      data-testid="trace-timeline"
      className={cn("w-full overflow-x-auto rounded-lg border bg-background", className)}
    >
      {/* legend */}
      <div className="flex flex-wrap items-center gap-4 border-b bg-muted/30 px-3 py-1.5 text-[11px] text-muted-foreground">
        <span className="font-medium text-foreground">{T.timeline}</span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-6 rounded-sm border-2 border-foreground/60 bg-transparent" />
          {T.criticalPath}
        </span>
        <span className="flex items-center gap-1">
          <span className={cn("inline-block h-3 w-6 rounded-sm border", GAP_CLASS)} />
          {T.gap}
        </span>
        <span className="ml-auto font-mono">
          {T.totalWall} {fmtMs(layout.wallMs)}
        </span>
      </div>

      {/* header */}
      <div
        className="flex h-6 items-center gap-2 border-b bg-muted/20 text-[11px] font-medium text-muted-foreground"
      >
        <div className="w-56 shrink-0 pl-2">{T.node}</div>
        <div className="relative min-w-0 flex-1">
          <div className="flex justify-between px-1 font-mono">
            <span>0ms</span>
            <span>{fmtMs(layout.wallMs / 2)}</span>
            <span>{fmtMs(layout.wallMs)}</span>
          </div>
        </div>
        <div className="flex w-32 shrink-0 justify-end gap-2 pr-2">
          <span>{T.duration}</span>
          <span className="w-12 text-right">{T.percent}</span>
        </div>
      </div>

      {/* 無 request root 的舊 trace：合成一列總覽列，承載 gap 顯示 */}
      {showSyntheticWall && (
        <div
          data-testid="timeline-row-__wall"
          className="flex h-8 items-center gap-2 border-b border-border/60 text-xs text-muted-foreground"
        >
          <div className="flex w-56 shrink-0 items-center gap-1 pl-2">
            <span className="h-4 w-4 shrink-0" />
            <span className="truncate italic">{T.totalWall}</span>
          </div>
          <div className="relative h-full min-w-0 flex-1">
            <div className="absolute top-1 bottom-1 left-0 w-full rounded-sm border border-dashed border-muted-foreground/30" />
            {layout.gaps.map((g, i) => (
              <Bar
                key={`gap-${i}`}
                seg={g}
                colorClass={GAP_CLASS}
                emphasised={false}
                testId={`timeline-gap-__wall-${i}`}
              />
            ))}
          </div>
          <div className="flex w-32 shrink-0 items-center justify-end gap-2 pr-2 font-mono">
            <span>{fmtMs(layout.wallMs)}</span>
            <span className="w-12 text-right">100%</span>
          </div>
        </div>
      )}

      <div>
        {visibleRows.map((row) => (
          <TimelineRowView
            key={row.nodeId}
            row={row}
            expanded={isExpanded(row)}
            onToggle={onToggle}
            onSelectNode={onSelectNode}
          />
        ))}
      </div>
    </div>
  );
}
