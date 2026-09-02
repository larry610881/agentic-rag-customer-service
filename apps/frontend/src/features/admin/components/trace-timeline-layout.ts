import type { ExecutionNode } from "@/types/agent-trace";

/**
 * Issue #57 — trace 時間軸（waterfall / Gantt）純排版計算。
 *
 * 不含任何 React / DOM 依賴，方便單元測試。所有百分比皆相對於
 * 「wall clock」：若存在 node_type === "request" 的 root 節點，wall clock =
 * root 的 [start_ms, end_ms]；否則 = [0, max(end_ms)]（全部節點皆無時長時退回
 * [0, total_ms]）。
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export const REQUEST_NODE_TYPE = "request";

export type TimelineSegment = {
  /** 對應節點 id；gap segment 為 null */
  nodeId: string | null;
  nodeType: string;
  label: string;
  startMs: number;
  endMs: number;
  durationMs: number;
  /** 相對 wall clock 的左緣百分比（0–100） */
  leftPct: number;
  /** 相對 wall clock 的寬度百分比（0–100） */
  widthPct: number;
  /** 佔 wall clock 的百分比（0–100） */
  percentOfWall: number;
  /** true = 未被任何子孫節點覆蓋的「其他／未儀表化」時間 */
  isGap: boolean;
};

export type TimelineRow = {
  nodeId: string;
  node: ExecutionNode;
  /** 樹狀縮排層級，root = 0 */
  depth: number;
  parentId: string | null;
  isRoot: boolean;
  startMs: number;
  endMs: number;
  durationMs: number;
  leftPct: number;
  widthPct: number;
  percentOfWall: number;
  /** 關鍵路徑：每一層在互相重疊的 sibling 中取時長最大者，沿此鏈往下 */
  isCriticalPath: boolean;
  hasChildren: boolean;
  /** 直接子節點依 start_ms 排序後的連續色塊（收合時 inline 顯示） */
  segments: TimelineSegment[];
  /** 任兩個直接子節點時間重疊 → 必須展開成子列，inline segment 會互相蓋住 */
  childrenOverlap: boolean;
  /** 只有 root row 會有值：wall clock 內未被任何子孫節點覆蓋的區間 */
  gaps: TimelineSegment[];
};

export type TimelineLayout = {
  rows: TimelineRow[];
  /** root row 的 nodeId（request 節點）；無 request 節點時為 null */
  rootId: string | null;
  wallStartMs: number;
  wallEndMs: number;
  wallMs: number;
  /**
   * wall clock 內未被任何節點覆蓋的區間。有 request root 時等同 root row 的
   * gaps；無 root 時仍會計算，讓元件可用合成的總覽列呈現。
   */
  gaps: TimelineSegment[];
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type Interval = { start: number; end: number };

/** 浮點雜訊容忍：小於此值的 gap 不視為未儀表化區間 */
const GAP_EPSILON_MS = 0.5;

function nodeInterval(n: ExecutionNode): Interval {
  const start = Number.isFinite(n.start_ms) ? n.start_ms : 0;
  let end = Number.isFinite(n.end_ms) ? n.end_ms : start;
  if (end < start) {
    // end_ms 缺失或壞掉時退回 duration_ms
    end = start + Math.max(n.duration_ms ?? 0, 0);
  }
  return { start, end };
}

function overlaps(a: Interval, b: Interval): boolean {
  // 嚴格比較：首尾相接（a.end === b.start）不算重疊
  return a.start < b.end && b.start < a.end;
}

function anyPairOverlaps(intervals: Interval[]): boolean {
  const sorted = [...intervals].sort((x, y) => x.start - y.start);
  let maxEnd = -Infinity;
  for (const iv of sorted) {
    if (iv.start < maxEnd) return true;
    maxEnd = Math.max(maxEnd, iv.end);
  }
  return false;
}

function clampPct(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.min(100, Math.max(0, v));
}

/**
 * 把區間合併後，回傳 [wallStart, wallEnd] 內未被覆蓋的區間。
 */
function computeUncovered(
  intervals: Interval[],
  wallStart: number,
  wallEnd: number,
): Interval[] {
  const sorted = intervals
    .filter((iv) => iv.end > iv.start)
    .sort((a, b) => a.start - b.start);
  const gaps: Interval[] = [];
  let cursor = wallStart;
  for (const iv of sorted) {
    if (iv.start > cursor + GAP_EPSILON_MS) {
      gaps.push({ start: cursor, end: Math.min(iv.start, wallEnd) });
    }
    cursor = Math.max(cursor, iv.end);
    if (cursor >= wallEnd) break;
  }
  if (cursor < wallEnd - GAP_EPSILON_MS) {
    gaps.push({ start: cursor, end: wallEnd });
  }
  return gaps.filter((g) => g.end - g.start > GAP_EPSILON_MS);
}

/**
 * 在一組 sibling 中挑出關鍵路徑節點：先把時間重疊的 sibling 聚成 cluster
 * （transitive：A-B 重疊、B-C 重疊 → A/B/C 同 cluster），每個 cluster 取時長最大者。
 * 無重疊的 sibling 自成 cluster，必然是關鍵路徑。
 */
function pickCriticalSiblings(
  siblings: { id: string; iv: Interval; duration: number; order: number }[],
): Set<string> {
  const result = new Set<string>();
  const sorted = [...siblings].sort(
    (a, b) => a.iv.start - b.iv.start || a.order - b.order,
  );
  let cluster: typeof sorted = [];
  let clusterEnd = -Infinity;
  const flush = () => {
    if (cluster.length === 0) return;
    let best = cluster[0];
    for (const c of cluster) {
      if (
        c.duration > best.duration ||
        (c.duration === best.duration && c.order < best.order)
      ) {
        best = c;
      }
    }
    result.add(best.id);
    cluster = [];
  };
  for (const s of sorted) {
    if (cluster.length > 0 && s.iv.start < clusterEnd) {
      cluster.push(s);
    } else {
      flush();
      cluster = [s];
    }
    clusterEnd = Math.max(clusterEnd, s.iv.end);
  }
  flush();
  return result;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export function buildTraceTimeline(
  nodes: ExecutionNode[],
  totalMs: number,
): TimelineLayout {
  const empty: TimelineLayout = {
    rows: [],
    rootId: null,
    wallStartMs: 0,
    wallEndMs: 0,
    wallMs: 0,
    gaps: [],
  };
  if (!nodes || nodes.length === 0) return empty;

  const byId = new Map<string, ExecutionNode>();
  const order = new Map<string, number>();
  nodes.forEach((n, i) => {
    byId.set(n.node_id, n);
    order.set(n.node_id, i);
  });
  const intervals = new Map<string, Interval>();
  for (const n of nodes) intervals.set(n.node_id, nodeInterval(n));

  // --- root 判定 -----------------------------------------------------------
  const root =
    nodes.find(
      (n) =>
        n.node_type === REQUEST_NODE_TYPE &&
        (n.parent_id == null || !byId.has(n.parent_id)),
    ) ?? null;

  // --- 建樹（無 parent 或 parent 找不到 → 掛在 root 下；無 root → top-level） ---
  const childrenOf = new Map<string, ExecutionNode[]>();
  const topLevel: ExecutionNode[] = [];
  for (const n of nodes) {
    if (root && n.node_id === root.node_id) continue;
    const parentId =
      n.parent_id && byId.has(n.parent_id) && n.parent_id !== n.node_id
        ? n.parent_id
        : root
          ? root.node_id
          : null;
    if (parentId == null) {
      topLevel.push(n);
    } else {
      const list = childrenOf.get(parentId) ?? [];
      list.push(n);
      childrenOf.set(parentId, list);
    }
  }
  const sortSiblings = (list: ExecutionNode[]) =>
    list.sort(
      (a, b) =>
        intervals.get(a.node_id)!.start - intervals.get(b.node_id)!.start ||
        order.get(a.node_id)! - order.get(b.node_id)!,
    );
  for (const list of childrenOf.values()) sortSiblings(list);
  sortSiblings(topLevel);

  // --- wall clock ----------------------------------------------------------
  let wallStart: number;
  let wallEnd: number;
  if (root) {
    const iv = intervals.get(root.node_id)!;
    wallStart = iv.start;
    wallEnd = iv.end;
    // root 若比子孫短（backend 補得不齊）→ 撐到子孫最大 end，避免溢出 100%
    for (const n of nodes) {
      if (n.node_id === root.node_id) continue;
      wallEnd = Math.max(wallEnd, intervals.get(n.node_id)!.end);
    }
  } else {
    wallStart = 0;
    wallEnd = 0;
    for (const iv of intervals.values()) wallEnd = Math.max(wallEnd, iv.end);
    if (wallEnd <= 0) wallEnd = Math.max(totalMs, 0);
  }
  const wallMs = Math.max(wallEnd - wallStart, 0);
  const toPct = (ms: number) => (wallMs > 0 ? (ms / wallMs) * 100 : 0);

  const makeSegment = (
    iv: Interval,
    meta: { nodeId: string | null; nodeType: string; label: string; isGap: boolean },
  ): TimelineSegment => {
    const duration = Math.max(iv.end - iv.start, 0);
    return {
      ...meta,
      startMs: iv.start,
      endMs: iv.end,
      durationMs: duration,
      leftPct: clampPct(toPct(iv.start - wallStart)),
      widthPct: clampPct(toPct(duration)),
      percentOfWall: clampPct(toPct(duration)),
    };
  };

  // --- 關鍵路徑 ------------------------------------------------------------
  const critical = new Set<string>();
  const siblingInfo = (list: ExecutionNode[]) =>
    list.map((n) => {
      const iv = intervals.get(n.node_id)!;
      return {
        id: n.node_id,
        iv,
        duration: iv.end - iv.start,
        order: order.get(n.node_id)!,
      };
    });
  const walkCritical = (list: ExecutionNode[]) => {
    if (list.length === 0) return;
    const picked = pickCriticalSiblings(siblingInfo(list));
    for (const id of picked) {
      critical.add(id);
      walkCritical(childrenOf.get(id) ?? []);
    }
  };
  if (root) {
    critical.add(root.node_id);
    walkCritical(childrenOf.get(root.node_id) ?? []);
  } else {
    walkCritical(topLevel);
  }

  // --- gaps（wall clock 內未被任何非 root 節點覆蓋） ------------------------
  const coverIntervals: Interval[] = [];
  for (const n of nodes) {
    if (root && n.node_id === root.node_id) continue;
    coverIntervals.push(intervals.get(n.node_id)!);
  }
  const gaps = computeUncovered(coverIntervals, wallStart, wallEnd).map((g) =>
    makeSegment(g, {
      nodeId: null,
      nodeType: "gap",
      label: "其他（未儀表化）",
      isGap: true,
    }),
  );

  // --- DFS 產生 rows -------------------------------------------------------
  const rows: TimelineRow[] = [];
  const visiting = new Set<string>();
  const emit = (n: ExecutionNode, depth: number, parentId: string | null) => {
    if (visiting.has(n.node_id)) return; // 防禦：循環 parent_id
    visiting.add(n.node_id);
    const iv = intervals.get(n.node_id)!;
    const children = childrenOf.get(n.node_id) ?? [];
    const isRoot = root != null && n.node_id === root.node_id;
    const base = makeSegment(iv, {
      nodeId: n.node_id,
      nodeType: n.node_type,
      label: n.label,
      isGap: false,
    });
    rows.push({
      nodeId: n.node_id,
      node: n,
      depth,
      parentId,
      isRoot,
      startMs: iv.start,
      endMs: iv.end,
      durationMs: base.durationMs,
      leftPct: base.leftPct,
      widthPct: base.widthPct,
      percentOfWall: base.percentOfWall,
      isCriticalPath: critical.has(n.node_id),
      hasChildren: children.length > 0,
      segments: children.map((c) =>
        makeSegment(intervals.get(c.node_id)!, {
          nodeId: c.node_id,
          nodeType: c.node_type,
          label: c.label,
          isGap: false,
        }),
      ),
      childrenOverlap: anyPairOverlaps(
        children.map((c) => intervals.get(c.node_id)!),
      ),
      gaps: isRoot ? gaps : [],
    });
    for (const c of children) emit(c, depth + 1, n.node_id);
  };
  if (root) {
    emit(root, 0, null);
  } else {
    for (const n of topLevel) emit(n, 0, null);
  }

  return {
    rows,
    rootId: root?.node_id ?? null,
    wallStartMs: wallStart,
    wallEndMs: wallEnd,
    wallMs,
    gaps,
  };
}

/** 判斷兩個 segment / row 是否時間重疊（匯出給測試與元件使用） */
export function segmentsOverlap(
  a: { startMs: number; endMs: number },
  b: { startMs: number; endMs: number },
): boolean {
  return overlaps({ start: a.startMs, end: a.endMs }, { start: b.startMs, end: b.endMs });
}
