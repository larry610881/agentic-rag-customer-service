import { useMemo } from "react";
import { ArrowLeft, Clock, Cpu, Layers } from "lucide-react";
import { formatDateTime } from "@/lib/format-date";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AgentTraceGraph } from "./agent-trace-graph";
import type { AgentExecutionTrace, ExecutionNode } from "@/types/agent-trace";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const MODE_LABELS: Record<string, string> = {
  react: "ReAct",
  supervisor: "Supervisor",
  meta_supervisor: "Meta Supervisor",
};

const NODE_TYPE_COLORS: Record<string, string> = {
  user_input: "#94a3b8",
  agent_llm: "#3b82f6",
  tool_call: "#10b981",
  tool_result: "#10b981",
  supervisor_dispatch: "#a855f7",
  meta_router: "#f59e0b",
  worker_execution: "#6366f1",
  final_response: "#22c55e",
  router: "#f59e0b",
};

function WaterfallChart({ nodes }: { nodes: ExecutionNode[] }) {
  const data = useMemo(() => {
    return nodes
      .filter((n) => n.duration_ms > 0)
      .map((n) => ({
        name: n.label.length > 20 ? n.label.slice(0, 20) + "..." : n.label,
        start: n.start_ms,
        duration: n.duration_ms,
        nodeType: n.node_type,
        fullLabel: n.label,
      }));
  }, [nodes]);

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        沒有時間資料
      </div>
    );
  }

  return (
    <div className="h-[400px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 10, right: 30, left: 120, bottom: 10 }}
        >
          <XAxis
            type="number"
            domain={[0, "dataMax"]}
            tickFormatter={(v: number) => `${v.toFixed(0)}ms`}
          />
          <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value: number | undefined) => [
              `${(value ?? 0).toFixed(0)}ms`,
            ]}
            labelFormatter={() => ""}
          />
          {/* Invisible bar for offset (start position) */}
          <Bar dataKey="start" stackId="a" fill="transparent" />
          <Bar dataKey="duration" stackId="a" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={NODE_TYPE_COLORS[entry.nodeType] ?? "#94a3b8"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

type AgentTraceDetailProps = {
  trace: AgentExecutionTrace;
  onBack: () => void;
};

export function AgentTraceDetail({ trace, onBack }: AgentTraceDetailProps) {
  const nodeCount = trace.nodes?.length ?? 0;
  const toolNodes = (trace.nodes ?? []).filter(
    (n) => n.node_type === "tool_call",
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回列表
        </Button>
      </div>

      {/* Summary Header */}
      <div className="flex flex-wrap gap-4 rounded-lg border bg-muted/30 p-4">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">
            {MODE_LABELS[trace.agent_mode] ?? trace.agent_mode}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="font-mono text-sm">{trace.total_ms.toFixed(0)}ms</span>
        </div>
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm">{nodeCount} 節點</span>
        </div>
        {toolNodes.length > 0 && (
          <Badge variant="outline">
            {toolNodes.length} 工具呼叫
          </Badge>
        )}
        {trace.conversation_id && (
          <span className="text-xs text-muted-foreground">
            Conversation: {trace.conversation_id.slice(0, 12)}...
          </span>
        )}
        <span className="text-xs text-muted-foreground">
          {formatDateTime(trace.created_at)}
        </span>
      </div>

      {/* Tabs: Graph / Timeline */}
      <Tabs defaultValue="graph">
        <TabsList>
          <TabsTrigger value="graph">節點圖</TabsTrigger>
          <TabsTrigger value="timeline">時間軸</TabsTrigger>
        </TabsList>
        <TabsContent value="graph" className="pt-2">
          <AgentTraceGraph execNodes={trace.nodes ?? []} />
        </TabsContent>
        <TabsContent value="timeline" className="pt-2">
          <WaterfallChart nodes={trace.nodes ?? []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
