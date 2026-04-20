import { useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Card } from "@/components/ui/card";
import { Activity } from "lucide-react";
import type { SSEEvent } from "@/lib/sse-client";
import type { ExecutionNode, ExecutionNodeType } from "@/types/agent-trace";
import {
  TraceNode,
  groupParallelByStartMs,
  type CustomNodeData,
} from "@/features/admin/components/agent-trace-graph";
import {
  getLayoutedElements,
  makeParallelGroupId,
} from "@/features/admin/lib/trace-layout";

const NODE_TYPES = { traceNode: TraceNode };

/**
 * 用 SSE event 串成 partial ExecutionNode list — 邏輯與後端 trace builder
 * 相似但簡化：沒有完整 metadata，只給「即時長 DAG」用。
 *
 * 規則：
 * - worker_routing → node_type=worker_routing，label="→ {worker_name}"
 * - tool_calls → 每個 tool 一個 node_type=tool_call，同 ts_ms = 平行群組
 * - sources → node_type=tool_result，attach 到最近一個 rag_query tool_call
 * - error → 把最後一個節點 outcome 標為 failed
 *
 * `done` 事件不在這處理，由 onTraceComplete 觸發外層 fetch 完整 trace。
 */
function appendEventToNodes(
  prev: ExecutionNode[],
  event: SSEEvent,
  syntheticIdSeed: number,
): ExecutionNode[] {
  const tsMs =
    typeof event.ts_ms === "number" && event.ts_ms > 0 ? event.ts_ms : 0;
  const baseId =
    typeof event.node_id === "string" && event.node_id
      ? (event.node_id as string)
      : `live-${syntheticIdSeed}`;

  const lastNode = prev[prev.length - 1];
  const lastTopLevel = [...prev]
    .reverse()
    .find((n) => n.parent_id === null);

  if (event.type === "worker_routing") {
    const workerName =
      typeof event.worker_name === "string"
        ? (event.worker_name as string)
        : "worker";
    return [
      ...prev,
      makeNode({
        id: baseId,
        type: "worker_routing",
        label: `→ ${workerName}`,
        parentId: null,
        startMs: tsMs,
        metadata: { selected_worker: workerName },
      }),
    ];
  }

  if (event.type === "tool_calls" && Array.isArray(event.tool_calls)) {
    const tools = event.tool_calls as Array<{ tool_name: string }>;
    const newNodes: ExecutionNode[] = tools.map((t, i) =>
      makeNode({
        id: `${baseId}::${i}`,
        type: "tool_call",
        label: t.tool_name,
        parentId: lastTopLevel?.node_id ?? null,
        startMs: tsMs,
        metadata: { tool_name: t.tool_name },
      }),
    );
    return [...prev, ...newNodes];
  }

  if (event.type === "sources" && Array.isArray(event.sources)) {
    // attach 到最近一個「rag_query / search」相關 tool_call
    const sources = event.sources as Array<Record<string, unknown>>;
    const ragParent = [...prev]
      .reverse()
      .find(
        (n) =>
          n.node_type === "tool_call" &&
          (n.label === "rag_query" || n.label.includes("rag")),
      );
    if (!ragParent) return prev;
    return [
      ...prev,
      makeNode({
        id: baseId,
        type: "tool_result",
        label: "RAG 向量搜尋",
        parentId: ragParent.node_id,
        startMs: tsMs,
        metadata: {
          result_count: sources.length,
          chunk_scores: sources.slice(0, 8).map((s, i) => ({
            rank: i + 1,
            score:
              typeof s.score === "number"
                ? Number((s.score as number).toFixed(4))
                : 0,
            preview:
              typeof s.content_snippet === "string"
                ? (s.content_snippet as string).slice(0, 80)
                : "",
          })),
        },
      }),
    ];
  }

  if (event.type === "error" && lastNode) {
    const errMsg =
      typeof event.message === "string" ? (event.message as string) : "錯誤";
    return prev.map((n, idx) =>
      idx === prev.length - 1
        ? {
            ...n,
            outcome: "failed" as const,
            metadata: { ...n.metadata, error_message: errMsg },
          }
        : n,
    );
  }

  return prev;
}

function makeNode(input: {
  id: string;
  type: ExecutionNodeType;
  label: string;
  parentId: string | null;
  startMs: number;
  metadata?: Record<string, unknown>;
}): ExecutionNode {
  return {
    node_id: input.id,
    node_type: input.type,
    label: input.label,
    parent_id: input.parentId,
    start_ms: input.startMs,
    end_ms: input.startMs,
    duration_ms: 0,
    token_usage: null,
    outcome: "success",
    metadata: input.metadata ?? {},
  };
}

/**
 * 即時版 buildGraph — 邏輯與 admin agent-trace-graph 共用：
 * 主線分群偵測平行 + 子節點 emit + 平行 tag，最後 dagre 自動排版。
 */
function buildLiveGraph(execNodes: ExecutionNode[]): {
  nodes: Node[];
  edges: Edge[];
} {
  if (!execNodes.length) return { nodes: [], edges: [] };

  const nodeMap = new Map(execNodes.map((n) => [n.node_id, n]));
  const mainLine = execNodes.filter(
    (n) => !n.parent_id || !nodeMap.has(n.parent_id),
  );
  const childrenOf = new Map<string, ExecutionNode[]>();
  for (const n of execNodes) {
    if (n.parent_id && nodeMap.has(n.parent_id)) {
      const list = childrenOf.get(n.parent_id) ?? [];
      list.push(n);
      childrenOf.set(n.parent_id, list);
    }
  }

  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const mainGroups = groupParallelByStartMs(mainLine);
  let prevGroupLastId: string | null = null;

  for (const group of mainGroups) {
    const isParallel = group.length > 1;
    for (const n of group) {
      const groupId = makeParallelGroupId(n.parent_id, n.start_ms);
      nodes.push({
        id: n.node_id,
        type: "traceNode",
        position: { x: 0, y: 0 },  // dagre 會覆寫
        data: {
          execNode: n,
          isParallelGroup: isParallel,
          parallelCount: group.length,
          parallelGroupId: isParallel ? groupId : undefined,
        } satisfies CustomNodeData,
        dragHandle: ".drag-handle",
      });
      if (prevGroupLastId) {
        edges.push({
          id: `e-seq-${prevGroupLastId}-${n.node_id}`,
          source: prevGroupLastId,
          target: n.node_id,
          animated: true,
          style: { stroke: isParallel ? "#a78bfa" : "#cbd5e1" },
        });
      }
      const children = childrenOf.get(n.node_id);
      if (children) {
        const childGroups = groupParallelByStartMs(children);
        for (const cgroup of childGroups) {
          const cIsParallel = cgroup.length > 1;
          for (const child of cgroup) {
            const childGroupId = makeParallelGroupId(
              child.parent_id,
              child.start_ms,
            );
            nodes.push({
              id: child.node_id,
              type: "traceNode",
              position: { x: 0, y: 0 },  // dagre 會覆寫
              data: {
                execNode: child,
                isParallelGroup: cIsParallel,
                parallelCount: cgroup.length,
                parallelGroupId: cIsParallel ? childGroupId : undefined,
              } satisfies CustomNodeData,
              dragHandle: ".drag-handle",
            });
            edges.push({
              id: `e-child-${n.node_id}-${child.node_id}`,
              source: n.node_id,
              target: child.node_id,
              animated: true,
              style: {
                stroke: cIsParallel ? "#a78bfa" : "#94a3b8",
                strokeDasharray: "5 3",
              },
            });
          }
        }
      }
    }
    prevGroupLastId = group[group.length - 1].node_id;
  }

  // 用 dagre 算 position（不重疊）+ post-process 保留平行群組同 column 視覺
  return getLayoutedElements(nodes, edges, { direction: "LR" });
}

type LiveTraceInnerProps = {
  events: SSEEvent[];
  resetSignal: number;
};

function LiveTraceInner({ events, resetSignal }: LiveTraceInnerProps) {
  const reactFlow = useReactFlow();
  const [execNodes, setExecNodes] = useState<ExecutionNode[]>([]);
  const processedCountRef = useRef(0);
  const seedRef = useRef(0);

  // events 重置（reset signal 變化、或長度變短）→ 清空節點
  useEffect(() => {
    setExecNodes([]);
    processedCountRef.current = 0;
    seedRef.current = 0;
  }, [resetSignal]);

  // 增量處理新事件
  useEffect(() => {
    if (events.length < processedCountRef.current) {
      processedCountRef.current = 0;
      setExecNodes([]);
    }
    if (events.length === processedCountRef.current) return;
    setExecNodes((prev) => {
      let next = prev;
      for (let i = processedCountRef.current; i < events.length; i++) {
        seedRef.current += 1;
        next = appendEventToNodes(next, events[i], seedRef.current);
      }
      return next;
    });
    processedCountRef.current = events.length;
  }, [events]);

  const { nodes: graphNodes, edges: graphEdges } = useMemo(
    () => buildLiveGraph(execNodes),
    [execNodes],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(graphNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graphEdges);

  useEffect(() => {
    setNodes(graphNodes);
    setEdges(graphEdges);
  }, [graphNodes, graphEdges, setNodes, setEdges]);

  // 自動置中：每次節點數變化，pan 到最後新增的節點
  useEffect(() => {
    if (graphNodes.length === 0) return;
    const latest = graphNodes[graphNodes.length - 1];
    reactFlow.setCenter(latest.position.x + 140, latest.position.y + 50, {
      duration: 300,
      zoom: 1,
    });
  }, [graphNodes, reactFlow]);

  return (
    <div style={{ height: 360 }} className="rounded-lg border bg-background">
      {graphNodes.length === 0 ? (
        <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
          對話開始後 DAG 節點會逐步長出
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={NODE_TYPES}
          fitView={false}
          minZoom={0.4}
          maxZoom={1.5}
          zoomOnScroll={false}
          zoomOnDoubleClick={false}
          preventScrolling={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      )}
    </div>
  );
}

export type LiveTraceGraphProps = {
  events: SSEEvent[];
  /** 變動時 reset 內部節點（例如清除對話、新一輪訊息開始） */
  resetSignal: number;
};

/**
 * 即時長 DAG — 每收到一筆 SSE event 就增量加節點 + pan 到新節點。
 * 與 admin AgentTraceGraph 共用 TraceNode + groupParallelByStartMs，視覺一致。
 * Stream 結束後可由父層另外 render AgentTraceGraph 顯示後端完整精確 layout。
 */
export function LiveTraceGraph(props: LiveTraceGraphProps) {
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium">
        <Activity className="h-4 w-4 text-emerald-500" />
        即時 DAG
        <span className="text-xs font-normal text-muted-foreground">
          每筆事件即時長節點，視窗自動 pan 到最新
        </span>
      </div>
      <ReactFlowProvider>
        <LiveTraceInner {...props} />
      </ReactFlowProvider>
    </Card>
  );
}
