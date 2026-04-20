import dagre from "@dagrejs/dagre";
import type { Node, Edge } from "@xyflow/react";
import type { ExecutionNode } from "@/types/agent-trace";

const DEFAULT_NODE_W = 240;
const DEFAULT_NODE_H = 100;
const PARALLEL_VERTICAL_GAP = 110;

export type LayoutOptions = {
  /** 主軸方向，預設 "LR"（左→右，與 trace「時序往右」一致）*/
  direction?: "LR" | "TB";
  nodeWidth?: number;
  nodeHeight?: number;
  /** dagre rank 之間的距離（同 direction 軸） */
  ranksep?: number;
  /** dagre 同 rank 節點間距（垂直軸） */
  nodesep?: number;
};

type ParallelAwareData = {
  execNode?: ExecutionNode;
  /** 由 buildGraph 標記：true 時節點屬於某個平行群組 */
  isParallelGroup?: boolean;
  /** 同 (parent_id, start_ms) 的節點共享同一個 group id；
   *  post-process 用此 id 反查群組，套用 same-x + stack-y。*/
  parallelGroupId?: string;
  parallelCount?: number;
};

/**
 * 用 dagre 對 ReactFlow nodes/edges 做自動 layout，回傳有 position 的新 nodes。
 *
 * Post-process：把標記為 `isParallelGroup` 且同 `parallelGroupId` 的節點拉回
 * 同一個 x（取群組內最小 x），y 以群組中心對稱往上下 stack，
 * 確保「⚡ 並行同 column」的視覺語意保留 — 既有 LLM parallel tool calls
 * 在 trace 視圖中呈現「同欄並排」，符合直覺。
 */
export function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {},
): { nodes: Node[]; edges: Edge[] } {
  if (nodes.length === 0) return { nodes, edges };

  const direction = options.direction ?? "LR";
  const w = options.nodeWidth ?? DEFAULT_NODE_W;
  const h = options.nodeHeight ?? DEFAULT_NODE_H;
  const ranksep = options.ranksep ?? 80;
  const nodesep = options.nodesep ?? 40;

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, ranksep, nodesep });

  for (const n of nodes) {
    g.setNode(n.id, { width: w, height: h });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }

  dagre.layout(g);

  // dagre 給的是 center coordinate，ReactFlow 用 top-left → 補位移
  const positioned: Node[] = nodes.map((n) => {
    const dn = g.node(n.id);
    if (!dn) return n;
    return {
      ...n,
      position: { x: dn.x - w / 2, y: dn.y - h / 2 },
    };
  });

  // ── Post-process: 平行群組拉回同 x + stack 不重疊 y ──
  const groups = new Map<string, Node[]>();
  for (const n of positioned) {
    const data = n.data as ParallelAwareData;
    if (!data.isParallelGroup || !data.parallelGroupId) continue;
    const list = groups.get(data.parallelGroupId) ?? [];
    list.push(n);
    groups.set(data.parallelGroupId, list);
  }

  for (const members of groups.values()) {
    if (members.length < 2) continue;
    // 取群組內最小 x 為共用 x（保留 dagre 對「該 group 該在哪個 rank」的判斷）
    const sharedX = Math.min(...members.map((m) => m.position.x));
    // y 以群組中心對稱往上下 stack
    const yCenter =
      members.reduce((sum, m) => sum + m.position.y, 0) / members.length;
    const startY =
      yCenter - ((members.length - 1) * PARALLEL_VERTICAL_GAP) / 2;
    members.forEach((m, idx) => {
      m.position = {
        x: sharedX,
        y: startY + idx * PARALLEL_VERTICAL_GAP,
      };
    });
  }

  return { nodes: positioned, edges };
}

/**
 * 建立 parallel group id — 同 parent + 同 start_ms（容忍 < 50ms）的兄弟視為一組。
 * 給 buildGraph / buildLiveGraph 在 emit 節點時打 tag 使用。
 */
export function makeParallelGroupId(
  parentId: string | null,
  startMs: number,
): string {
  // start_ms 量化到 50ms bucket，避免 51ms vs 49ms 算成不同 group
  const bucket = Math.floor(startMs / 50);
  return `${parentId ?? "__root__"}::${bucket}`;
}
