import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Brain,
  Wrench,
  MessageCircle,
  Router,
  Users,
  User,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { ExecutionNode, ExecutionNodeType } from "@/types/agent-trace";

const NODE_ICONS: Record<ExecutionNodeType, React.ElementType> = {
  user_input: User,
  router: Router,
  meta_router: Router,
  supervisor_dispatch: Users,
  agent_llm: Brain,
  tool_call: Wrench,
  tool_result: Wrench,
  final_response: MessageCircle,
  worker_execution: Users,
};

const NODE_COLORS: Record<ExecutionNodeType, string> = {
  user_input: "border-slate-400 bg-slate-50 dark:bg-slate-900",
  router: "border-amber-400 bg-amber-50 dark:bg-amber-950",
  meta_router: "border-amber-400 bg-amber-50 dark:bg-amber-950",
  supervisor_dispatch: "border-purple-400 bg-purple-50 dark:bg-purple-950",
  agent_llm: "border-blue-400 bg-blue-50 dark:bg-blue-950",
  tool_call: "border-emerald-400 bg-emerald-50 dark:bg-emerald-950",
  tool_result: "border-emerald-400 bg-emerald-50 dark:bg-emerald-950",
  final_response: "border-green-400 bg-green-50 dark:bg-green-950",
  worker_execution: "border-indigo-400 bg-indigo-50 dark:bg-indigo-950",
};

function durationColor(ms: number) {
  if (ms >= 2000) return "text-red-600 dark:text-red-400";
  if (ms >= 500) return "text-yellow-600 dark:text-yellow-400";
  return "text-green-600 dark:text-green-400";
}

function str(v: unknown): string {
  return String(v ?? "");
}

function MetadataDetails({ meta }: { meta: Record<string, unknown> }) {
  const fields: { key: string; label: string; wrap?: boolean; pre?: boolean }[] = [
    { key: "message_preview", label: "訊息", wrap: true },
    { key: "answer_preview", label: "回覆", wrap: true },
    { key: "decision", label: "決策" },
    { key: "tool_name", label: "工具" },
    { key: "selected_worker", label: "Worker" },
    { key: "selected_team", label: "Team" },
    { key: "user_role", label: "角色" },
  ];

  return (
    <div className="mt-2 space-y-1 text-xs text-muted-foreground max-h-48 overflow-y-auto">
      {fields.map((f) =>
        meta[f.key] ? (
          <p key={f.key} className={f.wrap ? "break-words" : undefined}>
            <span className="font-medium">{f.label}：</span>
            {str(meta[f.key])}
          </p>
        ) : null,
      )}
      {meta.tool_calls ? (
        <p>
          <span className="font-medium">工具：</span>
          {Array.isArray(meta.tool_calls)
            ? (meta.tool_calls as string[]).join(", ")
            : str(meta.tool_calls)}
        </p>
      ) : null}
      {meta.result_preview ? (
        <pre className="whitespace-pre-wrap break-words rounded bg-muted/50 p-1.5 max-h-32 overflow-y-auto">
          {str(meta.result_preview).slice(0, 300)}
        </pre>
      ) : null}
    </div>
  );
}

type CustomNodeData = {
  execNode: ExecutionNode;
};

function TraceNode({ data }: { data: CustomNodeData }) {
  const [expanded, setExpanded] = useState(false);
  const n = data.execNode;
  const Icon = NODE_ICONS[n.node_type] ?? Brain;
  const colorClass = NODE_COLORS[n.node_type] ?? "border-gray-400 bg-gray-50";
  const meta = n.metadata;
  const hasDetail =
    !!meta.answer_preview ||
    !!meta.result_preview ||
    !!meta.tool_calls ||
    !!meta.selected_worker ||
    !!meta.message_preview;

  return (
    <div
      className={`rounded-lg border-2 px-3 py-2 shadow-sm min-w-[180px] max-w-[320px] ${colorClass}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 opacity-70" />
        <span className="text-sm font-medium truncate">{n.label}</span>
        {n.duration_ms > 0 && (
          <span
            className={`ml-auto font-mono text-xs ${durationColor(n.duration_ms)}`}
          >
            {n.duration_ms.toFixed(0)}ms
          </span>
        )}
      </div>
      {n.token_usage && (
        <div className="mt-1 flex gap-2 text-xs text-muted-foreground">
          {n.token_usage.input_tokens != null && (
            <span>in:{n.token_usage.input_tokens}</span>
          )}
          {n.token_usage.output_tokens != null && (
            <span>out:{n.token_usage.output_tokens}</span>
          )}
        </div>
      )}
      {hasDetail && (
        <button
          type="button"
          className="mt-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
        >
          {expanded ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
          詳情
        </button>
      )}
      {expanded && <MetadataDetails meta={meta} />}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-gray-400"
      />
    </div>
  );
}

const nodeTypes = { traceNode: TraceNode };

function buildGraph(execNodes: ExecutionNode[]): {
  nodes: Node[];
  edges: Edge[];
} {
  if (!execNodes || execNodes.length === 0) return { nodes: [], edges: [] };

  // Compute depth for each node (sequential top-down layout)
  const nodeMap = new Map<string, ExecutionNode>();
  for (const n of execNodes) {
    nodeMap.set(n.node_id, n);
  }

  // Simple sequential layout: nodes arranged top-down in order
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const depthCount = new Map<number, number>();

  for (let i = 0; i < execNodes.length; i++) {
    const n = execNodes[i];
    // Compute depth from parent chain
    let depth = 0;
    if (n.parent_id && nodeMap.has(n.parent_id)) {
      // Child node: offset to the right
      const parentIdx = execNodes.findIndex(
        (p) => p.node_id === n.parent_id,
      );
      if (parentIdx >= 0) {
        depth = (depthCount.get(parentIdx) ?? 0) + 1;
      }
    }

    const col = depthCount.get(i) ?? 0;
    depthCount.set(i, col);

    nodes.push({
      id: n.node_id,
      type: "traceNode",
      position: { x: i * 280, y: col * 150 },
      data: { execNode: n } satisfies CustomNodeData,
    });

    // Edge from parent or from previous sequential node
    if (n.parent_id && nodeMap.has(n.parent_id)) {
      edges.push({
        id: `e-${n.parent_id}-${n.node_id}`,
        source: n.parent_id,
        target: n.node_id,
        animated: true,
        style: { stroke: "#94a3b8" },
      });
    } else if (i > 0) {
      // Sequential edge to previous node (if no parent)
      edges.push({
        id: `e-seq-${i}`,
        source: execNodes[i - 1].node_id,
        target: n.node_id,
        animated: true,
        style: { stroke: "#cbd5e1" },
      });
    }
  }

  return { nodes, edges };
}

type AgentTraceGraphProps = {
  execNodes: ExecutionNode[];
};

export function AgentTraceGraph({ execNodes }: AgentTraceGraphProps) {
  const { nodes, edges } = useMemo(() => buildGraph(execNodes), [execNodes]);

  const onInit = useCallback(
    (instance: { fitView: () => void }) => {
      setTimeout(() => instance.fitView(), 50);
    },
    [],
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        沒有節點資料
      </div>
    );
  }

  return (
    <div className="h-[500px] w-full rounded-lg border bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onInit={onInit}
        fitView
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
