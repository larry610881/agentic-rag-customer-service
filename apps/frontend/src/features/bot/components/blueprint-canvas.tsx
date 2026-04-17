import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Bot as BotIcon,
  Users,
  Wrench,
  FileText,
  XCircle,
} from "lucide-react";
import { JsonView, darkStyles } from "react-json-view-lite";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  NODE_COLORS_FAILED,
  PING_ONCE_CLASS,
} from "@/features/admin/lib/trace-node-style";

export type BlueprintAgentSpec = {
  id: string;          // "main" 或 worker_name (Phase 1: stream worker_routing 用 worker_name 對應)
  label: string;
  isMain: boolean;
  toolNames: string[];
  metadata?: Record<string, unknown>;
};

export type ChunkNodeSpec = {
  id: string;
  parentToolNodeId: string;
  documentName: string;
  score: number;
  snippet: string;
};

export type BlueprintCanvasProps = {
  agents: BlueprintAgentSpec[];
  /** 點亮的 agent id 集合（"main" or worker name） */
  activeAgentIds: Set<string>;
  /** 點亮的 tool name 集合（per-agent.tool 組合，key = "{agentId}::{toolName}"） */
  activeToolKeys: Set<string>;
  /** 失敗節點 id 集合（agent / tool 共用 key 命名） */
  failedNodeIds: Set<string>;
  /** 失敗訊息對應（key 同 failedNodeIds） */
  errorMessages: Record<string, string>;
  /** RAG 動態 chunk 節點（每次 sources event 加入） */
  chunkNodes: ChunkNodeSpec[];
};

type AgentNodeData = {
  spec: BlueprintAgentSpec;
  isLit: boolean;
  isFailed: boolean;
  errorMessage?: string;
  onInspect: (spec: BlueprintAgentSpec) => void;
};

type ToolNodeData = {
  toolName: string;
  agentId: string;
  isLit: boolean;
  isFailed: boolean;
  errorMessage?: string;
  onInspect: (info: { toolName: string; agentId: string }) => void;
};

type ChunkNodeData = {
  spec: ChunkNodeSpec;
  onInspect: (spec: ChunkNodeSpec) => void;
};

const AGENT_W = 200;
const AGENT_H = 90;
const TOOL_W = 150;
const TOOL_H = 44;
const CHUNK_W = 180;
const CHUNK_H = 56;
const COL_GAP = 240;
const ROW_GAP = 110;
const TOOL_VERTICAL_GAP = 60;

function AgentBlueprintNode({ data }: { data: AgentNodeData }) {
  const { spec, isLit, isFailed, errorMessage, onInspect } = data;
  return (
    <button
      type="button"
      title={errorMessage || (isLit ? `${spec.label}（執行中）` : spec.label)}
      onClick={() => onInspect(spec)}
      className={cn(
        "rounded-lg border-2 p-3 text-left transition-all duration-200 cursor-pointer",
        "hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400",
        spec.isMain ? "min-w-[200px]" : "min-w-[180px]",
        isFailed
          ? `${NODE_COLORS_FAILED} ${PING_ONCE_CLASS}`
          : isLit
            ? "border-violet-500 bg-violet-50 shadow-md scale-[1.03] dark:bg-violet-950"
            : "border-muted bg-muted/20 opacity-60",
      )}
    >
      <Handle type="source" position={Position.Right} className="!bg-gray-400" />
      <div className="flex items-center gap-2">
        {spec.isMain ? (
          <BotIcon className="h-4 w-4" />
        ) : (
          <Users className="h-4 w-4" />
        )}
        <span className="text-sm font-medium truncate">{spec.label}</span>
        {spec.isMain && (
          <span className="ml-auto rounded bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-700 dark:bg-violet-900 dark:text-violet-200">
            main
          </span>
        )}
        {isFailed && (
          <XCircle className="ml-auto h-4 w-4 text-red-600 dark:text-red-400" />
        )}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        {spec.toolNames.length} 個工具
      </div>
    </button>
  );
}

function ToolBlueprintNode({ data }: { data: ToolNodeData }) {
  const { toolName, agentId, isLit, isFailed, errorMessage, onInspect } = data;
  return (
    <button
      type="button"
      title={errorMessage || toolName}
      onClick={() => onInspect({ toolName, agentId })}
      className={cn(
        "flex items-center gap-1 rounded border px-2 py-1 text-xs transition-all duration-200 cursor-pointer min-w-[150px]",
        "hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400",
        isFailed
          ? `${NODE_COLORS_FAILED} ${PING_ONCE_CLASS}`
          : isLit
            ? "border-emerald-500 bg-emerald-100 text-emerald-900 shadow scale-[1.05] dark:bg-emerald-900 dark:text-emerald-100"
            : "border-muted bg-background text-muted-foreground opacity-60",
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <Handle type="source" position={Position.Right} className="!bg-gray-400" />
      <Wrench className="h-3 w-3 shrink-0" />
      <span className="truncate">{toolName}</span>
    </button>
  );
}

function ChunkNode({ data }: { data: ChunkNodeData }) {
  const { spec, onInspect } = data;
  const scoreColor =
    spec.score >= 0.7
      ? "text-green-700 dark:text-green-400"
      : spec.score >= 0.4
        ? "text-yellow-700 dark:text-yellow-400"
        : "text-red-700 dark:text-red-400";
  return (
    <button
      type="button"
      onClick={() => onInspect(spec)}
      title={spec.snippet}
      className={cn(
        "rounded border bg-gradient-to-br from-sky-50 to-cyan-50 p-2 text-left transition-shadow cursor-pointer",
        "hover:shadow dark:from-sky-950 dark:to-cyan-950 min-w-[180px]",
        "border-sky-300 dark:border-sky-700",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400",
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-sky-400" />
      <div className="flex items-center gap-1 text-[10px] font-medium">
        <FileText className="h-3 w-3 text-sky-600 dark:text-sky-400" />
        <span className="truncate">{spec.documentName || "chunk"}</span>
        <span className={cn("ml-auto font-mono", scoreColor)}>
          {spec.score.toFixed(2)}
        </span>
      </div>
      <div className="mt-0.5 truncate text-[10px] text-muted-foreground">
        {spec.snippet}
      </div>
    </button>
  );
}

const NODE_TYPES = {
  agent: AgentBlueprintNode,
  tool: ToolBlueprintNode,
  chunk: ChunkNode,
};

type InspectTarget =
  | { kind: "agent"; spec: BlueprintAgentSpec }
  | { kind: "tool"; toolName: string; agentId: string }
  | { kind: "chunk"; spec: ChunkNodeSpec };

export function BlueprintCanvas({
  agents,
  activeAgentIds,
  activeToolKeys,
  failedNodeIds,
  errorMessages,
  chunkNodes,
}: BlueprintCanvasProps) {
  const [inspect, setInspect] = useState<InspectTarget | null>(null);

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    agents.forEach((agent, agentIdx) => {
      const agentNodeId = `agent:${agent.id}`;
      const agentY = agentIdx * (AGENT_H + ROW_GAP);
      nodes.push({
        id: agentNodeId,
        type: "agent",
        position: { x: 0, y: agentY },
        data: {
          spec: agent,
          isLit: activeAgentIds.has(agent.id),
          isFailed: failedNodeIds.has(agentNodeId),
          errorMessage: errorMessages[agentNodeId],
          onInspect: (spec: BlueprintAgentSpec) =>
            setInspect({ kind: "agent", spec }),
        } satisfies AgentNodeData,
        draggable: false,
      });

      const toolCount = agent.toolNames.length;
      const totalH = toolCount * TOOL_H + (toolCount - 1) * 12;
      const startY = agentY + AGENT_H / 2 - totalH / 2;

      agent.toolNames.forEach((toolName, toolIdx) => {
        const toolNodeId = `tool:${agent.id}:${toolName}`;
        const toolKey = `${agent.id}::${toolName}`;
        nodes.push({
          id: toolNodeId,
          type: "tool",
          position: {
            x: COL_GAP,
            y: startY + toolIdx * (TOOL_H + 12),
          },
          data: {
            toolName,
            agentId: agent.id,
            isLit: activeToolKeys.has(toolKey),
            isFailed: failedNodeIds.has(toolNodeId),
            errorMessage: errorMessages[toolNodeId],
            onInspect: (info: { toolName: string; agentId: string }) =>
              setInspect({ kind: "tool", ...info }),
          } satisfies ToolNodeData,
          draggable: false,
        });
        edges.push({
          id: `e:${agentNodeId}->${toolNodeId}`,
          source: agentNodeId,
          target: toolNodeId,
          animated: activeToolKeys.has(toolKey),
        });
      });
    });

    return { nodes, edges };
  }, [agents, activeAgentIds, activeToolKeys, failedNodeIds, errorMessages]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(layoutEdges);

  // 重新計算 layout（agents/active 變更時）
  useEffect(() => {
    setNodes((prev) => {
      // 保留動態 chunk 節點，只取代 agent/tool 節點
      const chunkN = prev.filter((n) => n.type === "chunk");
      return [...layoutNodes, ...chunkN];
    });
    setEdges((prev) => {
      const chunkE = prev.filter((e) => e.id.startsWith("ec:"));
      return [...layoutEdges, ...chunkE];
    });
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  // 動態加 chunk 節點
  useEffect(() => {
    setNodes((prev) => {
      const existingChunkIds = new Set(
        prev.filter((n) => n.type === "chunk").map((n) => n.id),
      );
      const newOnes: Node[] = [];
      const positionsByParent: Record<string, number> = {};
      // 計算每個 parent 已有多少 chunk → 新 chunk 排在最後
      prev
        .filter((n) => n.type === "chunk")
        .forEach((n) => {
          const parent = (n.data as ChunkNodeData).spec.parentToolNodeId;
          positionsByParent[parent] = (positionsByParent[parent] ?? 0) + 1;
        });
      chunkNodes.forEach((c) => {
        const id = `chunk:${c.id}`;
        if (existingChunkIds.has(id)) return;
        const parentNode = prev.find((n) => n.id === c.parentToolNodeId);
        const baseX = (parentNode?.position.x ?? COL_GAP) + COL_GAP;
        const baseY = parentNode?.position.y ?? 0;
        const idx = positionsByParent[c.parentToolNodeId] ?? 0;
        positionsByParent[c.parentToolNodeId] = idx + 1;
        newOnes.push({
          id,
          type: "chunk",
          position: { x: baseX, y: baseY + idx * (CHUNK_H + 12) },
          data: {
            spec: c,
            onInspect: (spec: ChunkNodeSpec) =>
              setInspect({ kind: "chunk", spec }),
          } satisfies ChunkNodeData,
          draggable: false,
        });
      });
      if (newOnes.length === 0) return prev;
      return [...prev, ...newOnes];
    });
    setEdges((prev) => {
      const existingEdgeIds = new Set(prev.map((e) => e.id));
      const newEdges: Edge[] = [];
      chunkNodes.forEach((c) => {
        const id = `ec:${c.parentToolNodeId}->chunk:${c.id}`;
        if (existingEdgeIds.has(id)) return;
        newEdges.push({
          id,
          source: c.parentToolNodeId,
          target: `chunk:${c.id}`,
          animated: false,
        });
      });
      if (newEdges.length === 0) return prev;
      return [...prev, ...newEdges];
    });
  }, [chunkNodes, setNodes, setEdges]);

  return (
    <>
      <div style={{ height: 480 }} className="rounded-lg border bg-muted/10">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={NODE_TYPES}
          fitView
          minZoom={0.4}
          maxZoom={1.5}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <Dialog open={inspect !== null} onOpenChange={(o) => !o && setInspect(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {inspect?.kind === "agent"
                ? `Agent：${inspect.spec.label}`
                : inspect?.kind === "tool"
                  ? `Tool：${inspect.toolName}`
                  : inspect?.kind === "chunk"
                    ? `RAG Chunk #${inspect.spec.id}`
                    : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="text-xs max-h-[60vh] overflow-auto">
            {inspect?.kind === "agent" && (
              <JsonView
                data={{
                  id: inspect.spec.id,
                  label: inspect.spec.label,
                  isMain: inspect.spec.isMain,
                  tools: inspect.spec.toolNames,
                  metadata: inspect.spec.metadata ?? {},
                }}
                style={darkStyles}
              />
            )}
            {inspect?.kind === "tool" && (
              <JsonView
                data={{
                  toolName: inspect.toolName,
                  agentId: inspect.agentId,
                }}
                style={darkStyles}
              />
            )}
            {inspect?.kind === "chunk" && (
              <JsonView data={inspect.spec} style={darkStyles} />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// 給外部用：tool node id 規則（與 onChunkNode 對應 parent）
export const blueprintToolNodeId = (agentId: string, toolName: string) =>
  `tool:${agentId}:${toolName}`;
