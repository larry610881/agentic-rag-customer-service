import { ArrowLeft, Clock, Cpu, Layers } from "lucide-react";
import { formatDateTime } from "@/lib/format-date";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AgentTraceGraph } from "./agent-trace-graph";
import { TraceTimeline } from "./trace-timeline";
import type { AgentExecutionTrace } from "@/types/agent-trace";

const MODE_LABELS: Record<string, string> = {
  react: "ReAct",
  supervisor: "Supervisor",
  meta_supervisor: "Meta Supervisor",
};

type AgentTraceDetailProps = {
  trace: AgentExecutionTrace;
  onBack: () => void;
  /** 時間軸點擊節點時回呼（頁面目前沒有節點選取狀態，保留擴充點） */
  onSelectNode?: (nodeId: string) => void;
};

export function AgentTraceDetail({
  trace,
  onBack,
  onSelectNode,
}: AgentTraceDetailProps) {
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
        {trace.llm_model && (
          <Badge variant="secondary" className="font-mono text-xs">
            {trace.llm_provider ? `${trace.llm_provider}/` : ""}{trace.llm_model}
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

      {/* Tabs: DAG（預設）/ 時間軸（Issue #57 waterfall） */}
      <Tabs defaultValue="graph">
        <TabsList>
          <TabsTrigger value="graph">節點圖</TabsTrigger>
          <TabsTrigger value="timeline">時間軸</TabsTrigger>
        </TabsList>
        <TabsContent value="graph" className="pt-2">
          <AgentTraceGraph execNodes={trace.nodes ?? []} />
        </TabsContent>
        <TabsContent value="timeline" className="pt-2">
          <TraceTimeline
            nodes={trace.nodes ?? []}
            totalMs={trace.total_ms}
            onSelectNode={onSelectNode}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
