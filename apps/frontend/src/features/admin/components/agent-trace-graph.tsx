import { useCallback, useMemo, useState } from "react";
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
import { Brain, ChevronDown, ChevronRight } from "lucide-react";
import { JsonView, darkStyles } from "react-json-view-lite";
import "react-json-view-lite/dist/index.css";
import type { ExecutionNode } from "@/types/agent-trace";
import {
  NODE_COLORS,
  NODE_ICONS,
  durationColor,
} from "@/features/admin/lib/trace-node-style";

function str(v: unknown): string {
  return String(v ?? "");
}

function tryParseJson(v: unknown): unknown | null {
  if (v == null) return null;
  if (typeof v === "object") return v;
  if (typeof v === "string") {
    try {
      return JSON.parse(v);
    } catch {
      return null;
    }
  }
  return null;
}

function SmartPre({ value, className }: { value: unknown; className?: string }) {
  const parsed = tryParseJson(value);
  if (parsed !== null && typeof parsed === "object") {
    return (
      <div className={`rounded p-2 text-xs ${className ?? ""}`}>
        <JsonView data={parsed} style={darkStyles} />
      </div>
    );
  }

  // Mixed format: split by [XXXMessage] markers, render JSON parts with JsonView
  const text = str(value);
  const segments = text.split(/(\[(?:System|Human|AI|Tool)Message\])/);

  if (segments.length <= 1) {
    return (
      <pre className={`whitespace-pre-wrap break-words rounded p-2 text-xs ${className ?? ""}`}>
        {text}
      </pre>
    );
  }

  return (
    <div className={`rounded p-2 text-xs space-y-1 ${className ?? ""}`}>
      {segments.map((seg, i) => {
        if (/^\[(?:System|Human|AI|Tool)Message\]$/.test(seg)) {
          return (
            <span key={i} className="font-semibold text-purple-500 dark:text-purple-400">
              {seg}
            </span>
          );
        }
        const trimmed = seg.trim();
        if (!trimmed) return null;
        const jsonData = tryParseJson(trimmed);
        if (jsonData !== null && typeof jsonData === "object") {
          return <JsonView key={i} data={jsonData} style={darkStyles} />;
        }
        return (
          <pre key={i} className="whitespace-pre-wrap break-words">
            {seg}
          </pre>
        );
      })}
    </div>
  );
}

function MetadataDetails({ meta }: { meta: Record<string, unknown> }) {
  const fields: { key: string; label: string; wrap?: boolean }[] = [
    { key: "message_preview", label: "訊息", wrap: true },
    { key: "answer_preview", label: "回覆", wrap: true },
    { key: "decision", label: "決策" },
    { key: "tool_name", label: "工具" },
    { key: "selected_worker", label: "Worker" },
    { key: "worker_name", label: "Sub-agent" },
    { key: "worker_llm", label: "Sub-agent LLM" },
    { key: "worker_llm_provider", label: "Sub-agent Provider" },
    { key: "worker_kb_count", label: "Sub-agent KB 數" },
    { key: "selected_team", label: "Team" },
    { key: "user_role", label: "角色" },
    { key: "history_turns", label: "歷史輪數" },
    { key: "history_context", label: "歷史上下文", wrap: true },
    { key: "input_chunks", label: "輸入筆數" },
    { key: "output_chunks", label: "輸出筆數" },
    { key: "top_score", label: "最高分" },
    { key: "result_count", label: "召回筆數" },
  ];

  const chunkScores = meta.chunk_scores as { rank: number; score: number; preview: string }[] | undefined;

  return (
    <div className="nopan nodrag mt-2 space-y-1 text-xs text-muted-foreground max-h-[300px] overflow-y-auto">
      {fields.map((f) => {
        if (meta[f.key] == null) return null;
        const value = str(meta[f.key]);
        // History context: split by [用戶]/[助手] turns with visual separation
        if (f.key === "history_context" && value) {
          const turns = value.split(/(?=\[用戶\]|\[助手\])/).filter(Boolean);
          return (
            <div key={f.key}>
              <span className="font-medium">{f.label}（{turns.length} 段）：</span>
              <div className="mt-1 space-y-1.5 max-h-[400px] overflow-y-auto">
                {turns.map((turn, ti) => {
                  const isUser = turn.startsWith("[用戶]");
                  return (
                    <div
                      key={ti}
                      className={`rounded p-1.5 text-xs ${isUser ? "bg-blue-50 dark:bg-blue-950 border-l-2 border-blue-400" : "bg-green-50 dark:bg-green-950 border-l-2 border-green-400"}`}
                    >
                      <span className={`font-semibold ${isUser ? "text-blue-600 dark:text-blue-400" : "text-green-600 dark:text-green-400"}`}>
                        {isUser ? "用戶" : "助手"}
                      </span>
                      <pre className="mt-0.5 whitespace-pre-wrap break-words text-xs">
                        {turn.replace(/^\[用戶\]\s*/, "").replace(/^\[助手\]\s*/, "")}
                      </pre>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        }
        if (f.wrap && value.includes("\n")) {
          return (
            <div key={f.key}>
              <span className="font-medium">{f.label}：</span>
              <pre className="mt-1 whitespace-pre-wrap break-words rounded bg-muted/50 p-1.5 text-xs">
                {value}
              </pre>
            </div>
          );
        }
        return (
          <p key={f.key} className={f.wrap ? "break-words" : undefined}>
            <span className="font-medium">{f.label}：</span>
            {value}
          </p>
        );
      })}
      {meta.tool_calls ? (
        <p>
          <span className="font-medium">工具：</span>
          {Array.isArray(meta.tool_calls)
            ? (meta.tool_calls as string[]).join(", ")
            : str(meta.tool_calls)}
        </p>
      ) : null}
      {chunkScores && chunkScores.length > 0 && (
        <div>
          <span className="font-medium">各段分數（共 {chunkScores.length} 筆）：</span>
          <div className="mt-1 space-y-0.5">
            {chunkScores.map((c) => (
              <div key={c.rank} className="flex gap-2">
                <span className="shrink-0 font-mono w-8 text-right">#{c.rank}</span>
                <span className={`shrink-0 font-mono w-14 text-right ${c.score >= 0.5 ? "text-green-600 dark:text-green-400" : "text-yellow-600 dark:text-yellow-400"}`}>
                  {c.score.toFixed(4)}
                </span>
                <span className="truncate opacity-70">{c.preview}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {meta.result_preview ? (
        <SmartPre value={meta.result_preview} className="bg-muted/50" />
      ) : null}
    </div>
  );
}

type CustomNodeData = {
  execNode: ExecutionNode;
};

function TraceNode({ data }: { data: CustomNodeData }) {
  const [expanded, setExpanded] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const n = data.execNode;
  const Icon = NODE_ICONS[n.node_type] ?? Brain;
  const colorClass =
    NODE_COLORS[n.node_type] ??
    "border-gray-400 bg-gray-50 dark:bg-gray-900";
  const meta = n.metadata;
  const hasDetail =
    !!meta.answer_preview ||
    !!meta.result_preview ||
    !!meta.tool_calls ||
    !!meta.selected_worker ||
    !!meta.message_preview ||
    !!meta.chunk_scores ||
    !!meta.input_chunks;
  const hasRaw = !!meta.llm_input || !!meta.llm_output;

  return (
    <div
      className={`rounded-lg border-2 px-3 py-2 shadow-sm min-w-[180px] ${showRaw ? "max-w-[600px]" : expanded ? "max-w-[500px]" : "max-w-[280px]"} ${colorClass}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <div className="drag-handle flex items-center gap-2 cursor-grab active:cursor-grabbing">
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
      {expanded && hasRaw && (
        <div className="nopan nodrag mt-1">
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setShowRaw(!showRaw);
            }}
          >
            {showRaw ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            Input / Output 原文
          </button>
          {showRaw && (
            <div className="nopan nodrag mt-2 space-y-2 text-xs max-h-[400px] overflow-y-auto">
              {meta.llm_input && (
                <div>
                  <span className="font-medium text-blue-600 dark:text-blue-400">Input:</span>
                  <SmartPre value={meta.llm_input} className="mt-1 bg-blue-50 dark:bg-blue-950" />
                </div>
              )}
              {meta.llm_output && (
                <div>
                  <span className="font-medium text-green-600 dark:text-green-400">Output:</span>
                  <SmartPre value={meta.llm_output} className="mt-1 bg-green-50 dark:bg-green-950" />
                </div>
              )}
            </div>
          )}
        </div>
      )}
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

  const nodeMap = new Map<string, ExecutionNode>();
  for (const n of execNodes) {
    nodeMap.set(n.node_id, n);
  }

  // Separate main-line nodes (no parent) and child nodes (have parent)
  const mainLine: ExecutionNode[] = [];
  const childrenOf = new Map<string, ExecutionNode[]>();

  for (const n of execNodes) {
    if (n.parent_id && nodeMap.has(n.parent_id)) {
      const siblings = childrenOf.get(n.parent_id) ?? [];
      siblings.push(n);
      childrenOf.set(n.parent_id, siblings);
    } else {
      mainLine.push(n);
    }
  }

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Layout main-line nodes horizontally
  for (let i = 0; i < mainLine.length; i++) {
    const n = mainLine[i];
    nodes.push({
      id: n.node_id,
      type: "traceNode",
      position: { x: i * 300, y: 0 },
      data: { execNode: n } satisfies CustomNodeData,
      dragHandle: ".drag-handle",
    });

    // Sequential edge
    if (i > 0) {
      edges.push({
        id: `e-seq-${i}`,
        source: mainLine[i - 1].node_id,
        target: n.node_id,
        animated: true,
        style: { stroke: "#cbd5e1" },
      });
    }

    // Layout child nodes vertically below parent
    const children = childrenOf.get(n.node_id);
    if (children) {
      for (let j = 0; j < children.length; j++) {
        const child = children[j];
        nodes.push({
          id: child.node_id,
          type: "traceNode",
          position: { x: i * 300 + j * 280, y: 160 },
          data: { execNode: child } satisfies CustomNodeData,
          dragHandle: ".drag-handle",
        });

        // Edge from parent to child
        edges.push({
          id: `e-child-${n.node_id}-${child.node_id}`,
          source: n.node_id,
          target: child.node_id,
          animated: true,
          style: { stroke: "#94a3b8", strokeDasharray: "5 3" },
        });

        // Sequential edge between siblings
        if (j > 0) {
          edges.push({
            id: `e-sibling-${j}`,
            source: children[j - 1].node_id,
            target: child.node_id,
            animated: true,
            style: { stroke: "#94a3b8" },
          });
        }
      }
    }
  }

  return { nodes, edges };
}

type AgentTraceGraphProps = {
  execNodes: ExecutionNode[];
};

export function AgentTraceGraph({ execNodes }: AgentTraceGraphProps) {
  const initial = useMemo(() => buildGraph(execNodes), [execNodes]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  // Sync when execNodes change
  useMemo(() => {
    setNodes(initial.nodes);
    setEdges(initial.edges);
  }, [initial]); // eslint-disable-line react-hooks/exhaustive-deps

  const onInit = useCallback(
    (instance: { fitView: () => void }) => {
      setTimeout(() => instance.fitView(), 50);
    },
    [],
  );

  if (initial.nodes.length === 0) {
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
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onInit={onInit}
        fitView
        minZoom={0.3}
        maxZoom={2}
        zoomOnScroll={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
