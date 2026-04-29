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
  NODE_COLORS_FAILED,
  NODE_ICONS,
  PING_ONCE_CLASS,
  durationColor,
} from "@/features/admin/lib/trace-node-style";
import {
  getLayoutedElements,
  makeParallelGroupId,
} from "@/features/admin/lib/trace-layout";
import { cn } from "@/lib/utils";

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

/**
 * 對話歷史載入區塊 — 明確區分 3 種狀態避免 user 看「歷史輪數: 8」就誤以為已載入。
 * - loaded：正常（綠色）
 * - empty：首輪對話沒有歷史（灰色）
 * - lost：歷史輪數 > 0 但 context 空 → backend regression 警示（紅色）
 */
function HistoryLoadBlock({
  turns,
  status,
  context,
  chars,
}: {
  turns: number;
  status?: "loaded" | "empty" | "lost";
  context: string;
  chars?: number;
}) {
  // status 沒帶（舊 trace 版本 backward compat）→ 從 turns + context 推導
  const effective: "loaded" | "empty" | "lost" =
    status ??
    (turns === 0 ? "empty" : context ? "loaded" : "lost");

  const badge =
    effective === "loaded" ? (
      <span className="rounded bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
        ✓ 已載入 {chars != null ? `(${chars} 字)` : ""}
      </span>
    ) : effective === "empty" ? (
      <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
        首輪對話
      </span>
    ) : (
      <span
        className="rounded bg-destructive/15 px-1.5 py-0.5 text-[11px] font-semibold text-destructive"
        title="歷史輪數 > 0 但載入給 LLM 的 context 為空 — backend 處理鏈可能斷掉"
      >
        ⚠ 上下文遺失
      </span>
    );

  const turnsList =
    context && context.trim()
      ? context.split(/(?=\[用戶\]|\[助手\])/).filter(Boolean)
      : [];

  return (
    <div className="rounded border-l-2 border-muted-foreground/30 pl-2 pb-1">
      <div className="flex items-center gap-2">
        <span className="font-medium">歷史輪數：</span>
        <span>{turns}</span>
        {badge}
      </div>
      {effective === "lost" && (
        <p className="mt-1 text-[11px] text-destructive">
          ⚠ 偵測到 history 有 {turns} 條 messages，但載入給 LLM 的 context
          字串為空。可能原因：history strategy 未注入 / 策略 process 失敗 /
          messages 內容空。LLM 此次回覆可能未參考歷史對話。
        </p>
      )}
      {turnsList.length > 0 && (
        <div className="mt-1 space-y-1.5 max-h-[400px] overflow-y-auto">
          <span className="font-medium text-[11px]">
            上下文（{turnsList.length} 段）：
          </span>
          {turnsList.map((turn, ti) => {
            const isUser = turn.startsWith("[用戶]");
            return (
              <div
                key={ti}
                className={`rounded p-1.5 text-[11px] ${
                  isUser
                    ? "bg-blue-50 dark:bg-blue-950 border-l-2 border-blue-400"
                    : "bg-green-50 dark:bg-green-950 border-l-2 border-green-400"
                }`}
              >
                <span
                  className={`font-semibold ${
                    isUser
                      ? "text-blue-600 dark:text-blue-400"
                      : "text-green-600 dark:text-green-400"
                  }`}
                >
                  {isUser ? "用戶" : "助手"}
                </span>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px]">
                  {turn
                    .replace(/^\[用戶\]\s*/, "")
                    .replace(/^\[助手\]\s*/, "")}
                </pre>
              </div>
            );
          })}
        </div>
      )}
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
    // history_* 三欄一起顯示用，下方 history block 會合併渲染後 skip 自身
    { key: "history_turns", label: "歷史輪數" },
    { key: "history_context", label: "歷史上下文", wrap: true },
    { key: "input_chunks", label: "輸入筆數" },
    { key: "output_chunks", label: "輸出筆數" },
    { key: "top_score", label: "最高分" },
    { key: "result_count", label: "召回筆數" },
  ];

  const chunkScores = meta.chunk_scores as { rank: number; score: number; preview: string }[] | undefined;

  // 整合的歷史載入區塊：明確標示「正常載入 / 首輪 / regression 警示」
  const historyTurns = meta.history_turns as number | undefined;
  const historyStatus = meta.history_loaded_status as
    | "loaded"
    | "empty"
    | "lost"
    | undefined;
  const historyContext = (meta.history_context as string | undefined) ?? "";
  const historyChars = meta.history_context_chars as number | undefined;
  const showHistoryBlock = historyTurns != null;

  return (
    <div className="nopan nodrag mt-2 space-y-1 text-xs text-muted-foreground max-h-[300px] overflow-y-auto">
      {showHistoryBlock && (
        <HistoryLoadBlock
          turns={historyTurns ?? 0}
          status={historyStatus}
          context={historyContext}
          chars={historyChars}
        />
      )}
      {fields.map((f) => {
        // history block 已整合成 HistoryLoadBlock 渲染，跳過原始 fields
        if (f.key === "history_turns" || f.key === "history_context") {
          return null;
        }
        if (meta[f.key] == null) return null;
        const value = str(meta[f.key]);
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

export type CustomNodeData = {
  execNode: ExecutionNode;
  /** 同 type + 同 start_ms 的相鄰節點視為平行群組 — true 時顯示 ⚡ badge */
  isParallelGroup?: boolean;
  /** 平行群組總共有幾個節點（含自己） */
  parallelCount?: number;
  /** 同 (parent_id, start_ms bucket) 的節點共享，給 trace-layout post-process 反查群組 */
  parallelGroupId?: string;
};

export function TraceNode({ data }: { data: CustomNodeData }) {
  const [expanded, setExpanded] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const n = data.execNode;
  const isFailed = n.outcome === "failed";
  const isParallel = data.isParallelGroup === true;
  const parallelCount = data.parallelCount ?? 1;
  const Icon = NODE_ICONS[n.node_type] ?? Brain;
  const colorClass = isFailed
    ? NODE_COLORS_FAILED
    : NODE_COLORS[n.node_type] ??
      "border-gray-400 bg-gray-50 dark:bg-gray-900";
  const meta = n.metadata;
  const errorMessage =
    typeof meta.error_message === "string" ? meta.error_message : "";
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
      title={errorMessage || undefined}
      className={cn(
        "rounded-lg border-2 px-3 py-2 shadow-sm min-w-[180px]",
        showRaw ? "max-w-[600px]" : expanded ? "max-w-[500px]" : "max-w-[280px]",
        colorClass,
        isFailed && PING_ONCE_CLASS,
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <div className="drag-handle flex items-center gap-2 cursor-grab active:cursor-grabbing">
        <Icon
          className={cn(
            "h-4 w-4 shrink-0",
            isFailed ? "text-red-600 dark:text-red-400" : "opacity-70",
          )}
        />
        <span className="text-sm font-medium truncate">{n.label}</span>
        {isParallel && (
          <span
            title={`平行呼叫（共 ${parallelCount} 個工具同時執行）`}
            className="rounded bg-violet-100 px-1 py-0.5 text-[10px] font-medium text-violet-700 dark:bg-violet-900 dark:text-violet-200"
          >
            ⚡ 並行
          </span>
        )}
        {isFailed && (
          <span className="rounded bg-red-100 px-1 py-0.5 text-[10px] font-medium text-red-700 dark:bg-red-900 dark:text-red-200">
            FAILED
          </span>
        )}
        {n.duration_ms > 0 && (
          <span
            className={`ml-auto font-mono text-xs ${durationColor(n.duration_ms)}`}
          >
            {n.duration_ms.toFixed(0)}ms
          </span>
        )}
      </div>
      {isFailed && errorMessage && (
        <div className="mt-1 rounded bg-red-100 px-2 py-1 text-xs text-red-800 dark:bg-red-900 dark:text-red-200">
          {errorMessage}
        </div>
      )}
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

/**
 * 把連續的同 type + 同 start_ms（差距 < 50ms 容忍）節點群組為 parallel group。
 * 避免把不相關的 start_ms=0 節點（如 user_input + worker_routing）誤合，
 * 只有「相鄰」且「節點類型一致」的視為真正的平行呼叫。
 */
export function groupParallelByStartMs(nodes: ExecutionNode[]): ExecutionNode[][] {
  const groups: ExecutionNode[][] = [];
  let current: ExecutionNode[] = [];
  for (const n of nodes) {
    const last = current[current.length - 1];
    if (
      last &&
      n.node_type === last.node_type &&
      Math.abs(n.start_ms - last.start_ms) < 50
    ) {
      current.push(n);
    } else {
      if (current.length > 0) groups.push(current);
      current = [n];
    }
  }
  if (current.length > 0) groups.push(current);
  return groups;
}

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

  // 主線按「相鄰同 type 同 start_ms」分組 — dagre 不知道哪些是「並行 sibling」，
  // 我們在 emit 節點時打 isParallelGroup + parallelGroupId tag，
  // 讓 trace-layout post-process 把同 group 拉回同 x + stack y。
  const mainGroups = groupParallelByStartMs(mainLine);
  let prevGroupLastNodeId: string | null = null;

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

      // Sequential edge from 前一個 group 的最後一個節點 → 本 group 的每個並行節點
      if (prevGroupLastNodeId) {
        edges.push({
          id: `e-seq-${prevGroupLastNodeId}-${n.node_id}`,
          source: prevGroupLastNodeId,
          target: n.node_id,
          animated: true,
          style: { stroke: isParallel ? "#a78bfa" : "#cbd5e1" },
        });
      }

      // 子節點（tool_result 等）— 同樣 emit 並打 parallel tag，dagre 自動排版
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

    // 取本 group 的最後一個節點當下一輪 sequential edge 的 source
    prevGroupLastNodeId = group[group.length - 1].node_id;
  }

  // 用 dagre 算 position（不重疊）+ post-process 保留平行群組同 column 視覺
  return getLayoutedElements(nodes, edges, { direction: "LR" });
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
