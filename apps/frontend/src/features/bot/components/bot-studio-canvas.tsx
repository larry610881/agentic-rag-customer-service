import { useCallback, useMemo, useState } from "react";
import { Send, Sparkles, Bot as BotIcon, Wrench, Users } from "lucide-react";
import type { SSEEvent } from "@/lib/sse-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { useWorkers } from "@/hooks/queries/use-workers";
import { useBuiltInTools } from "@/hooks/queries/use-built-in-tools";
import { useAgentTraceDetail } from "@/hooks/queries/use-agent-traces";
import { AgentTraceGraph } from "@/features/admin/components/agent-trace-graph";
import { useStudioStreaming } from "@/features/bot/hooks/use-studio-streaming";
import { getToolLabel } from "@/constants/tool-labels";
import type { Bot } from "@/types/bot";
import { cn } from "@/lib/utils";

type AgentNodeViewModel = {
  id: string;
  label: string;
  toolNames: string[];
  isMain: boolean;
};

type BotStudioCanvasProps = {
  bot: Bot;
};

const STREAM_RESET_LIMIT = 80;

/**
 * Bot Studio Canvas — 設定即時試運轉。
 *
 * 上半：BlueprintPanel 顯示 main agent + workers + 各自配置的 tools（dim by default）。
 * 中間：聊天輸入 + 演示模式 Switch（on 時每事件間隔 800ms）。
 * 下半：執行紀錄即時 feed + 結束後完整 DAG（reuse AgentTraceGraph）。
 *
 * Source 識別：自動帶 identity_source="studio" 寫入 trace.source，
 * 跟正式 web/widget/line 對話分流；feedback 按鈕在這層被禁掉（hideFeedback）。
 */
export function BotStudioCanvas({ bot }: BotStudioCanvasProps) {
  const { data: workers = [] } = useWorkers(bot.id);
  const { data: builtInTools = [] } = useBuiltInTools();

  const [message, setMessage] = useState("");
  const [slowMode, setSlowMode] = useState(false);
  const [activeNodeIds, setActiveNodeIds] = useState<Set<string>>(new Set());
  const [eventLog, setEventLog] = useState<SSEEvent[]>([]);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [assistantText, setAssistantText] = useState("");

  const builtInToolByName = useMemo(() => {
    const m = new Map<string, { label: string }>();
    for (const t of builtInTools) m.set(t.name, { label: t.label });
    return m;
  }, [builtInTools]);

  const agentNodes: AgentNodeViewModel[] = useMemo(() => {
    const main: AgentNodeViewModel = {
      id: "main",
      label: bot.name || "Main Agent",
      toolNames: bot.enabled_tools ?? [],
      isMain: true,
    };
    const workerNodes: AgentNodeViewModel[] = workers.map((w) => ({
      id: w.id,
      label: w.name,
      toolNames: w.enabled_tools ?? bot.enabled_tools ?? [],
      isMain: false,
    }));
    return [main, ...workerNodes];
  }, [bot.name, bot.enabled_tools, workers]);

  const { data: completedTrace } = useAgentTraceDetail(traceId);
  const { sendMessage, isStreaming } = useStudioStreaming({
    onEvent: (event) => {
      setEventLog((prev) =>
        prev.length >= STREAM_RESET_LIMIT ? prev : [...prev, event],
      );
      if (event.type === "token" && typeof event.content === "string") {
        setAssistantText((t) => t + event.content);
      }
      if (event.type === "tool_calls" && Array.isArray(event.tool_calls)) {
        const calls = event.tool_calls as Array<{ tool_name: string }>;
        setActiveNodeIds((prev) => {
          const next = new Set(prev);
          for (const c of calls) next.add(`tool:${c.tool_name}`);
          return next;
        });
      }
      if (event.type === "status" && typeof event.status === "string") {
        // 點亮 main agent（簡化版：所有 status 都歸到 main，未來可依 trace event 補 worker_id）
        setActiveNodeIds((prev) => {
          const next = new Set(prev);
          next.add("agent:main");
          return next;
        });
      }
    },
    onTraceComplete: (id) => setTraceId(id),
    onError: (err) => {
      console.error("[Studio] streaming error:", err);
    },
  });

  const handleSend = useCallback(() => {
    if (!message.trim() || isStreaming) return;
    setActiveNodeIds(new Set(["agent:main"]));
    setEventLog([]);
    setTraceId(null);
    setAssistantText("");
    void sendMessage({ message: message.trim(), botId: bot.id, slowMode });
    setMessage("");
  }, [message, isStreaming, sendMessage, bot.id, slowMode]);

  return (
    <div className="space-y-4">
      <BlueprintPanel
        agents={agentNodes}
        builtInToolByName={builtInToolByName}
        activeNodeIds={activeNodeIds}
      />

      <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3">
        <Input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="輸入測試訊息（例：你好 / 查產品 / 退貨流程）"
          disabled={isStreaming}
          className="flex-1"
        />
        <div className="flex items-center gap-2">
          <Switch
            id="studio-slow-mode"
            checked={slowMode}
            onCheckedChange={setSlowMode}
            disabled={isStreaming}
          />
          <Label
            htmlFor="studio-slow-mode"
            className="cursor-pointer text-xs text-muted-foreground"
          >
            演示模式
          </Label>
        </div>
        <Button onClick={handleSend} disabled={isStreaming || !message.trim()}>
          <Send className="mr-1 h-4 w-4" />
          送出
        </Button>
      </div>

      {(eventLog.length > 0 || assistantText) && (
        <ExecutionFeed events={eventLog} assistantText={assistantText} />
      )}

      {completedTrace && (
        <Card className="p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Sparkles className="h-4 w-4 text-violet-500" />
            完整執行 DAG
            <span className="ml-auto text-xs text-muted-foreground">
              {completedTrace.total_ms.toFixed(0)} ms · trace_id={" "}
              <code className="font-mono">{completedTrace.trace_id.slice(0, 8)}</code>
            </span>
          </div>
          <AgentTraceGraph execNodes={completedTrace.nodes} />
        </Card>
      )}
    </div>
  );
}

type BlueprintPanelProps = {
  agents: AgentNodeViewModel[];
  builtInToolByName: Map<string, { label: string }>;
  activeNodeIds: Set<string>;
};

function BlueprintPanel({
  agents,
  builtInToolByName,
  activeNodeIds,
}: BlueprintPanelProps) {
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium">
        <Sparkles className="h-4 w-4 text-violet-500" />
        Bot 配置藍圖
        <span className="text-xs font-normal text-muted-foreground">
          {agents.length} agent / 對話開始後對應節點會點亮
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => {
          const agentKey = agent.isMain ? "agent:main" : `agent:${agent.id}`;
          const isActive = activeNodeIds.has(agentKey);
          return (
            <div
              key={agent.id}
              className={cn(
                "rounded-lg border-2 p-3 transition-all duration-300",
                isActive
                  ? "border-violet-500 bg-violet-50 shadow-md scale-[1.02] dark:bg-violet-950"
                  : "border-muted bg-muted/20 opacity-70",
              )}
            >
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                {agent.isMain ? (
                  <BotIcon className="h-4 w-4" />
                ) : (
                  <Users className="h-4 w-4" />
                )}
                {agent.label}
                {agent.isMain && (
                  <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-700 dark:bg-violet-900 dark:text-violet-200">
                    main
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {agent.toolNames.length === 0 && (
                  <span className="text-xs text-muted-foreground">
                    無啟用工具
                  </span>
                )}
                {agent.toolNames.map((toolName) => {
                  const isToolActive = activeNodeIds.has(`tool:${toolName}`);
                  return (
                    <div
                      key={toolName}
                      className={cn(
                        "flex items-center gap-1 rounded border px-2 py-0.5 text-xs transition-all duration-300",
                        isToolActive
                          ? "border-emerald-500 bg-emerald-100 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-100"
                          : "border-muted bg-background text-muted-foreground",
                      )}
                    >
                      <Wrench className="h-3 w-3" />
                      {builtInToolByName.get(toolName)?.label ??
                        getToolLabel(toolName)}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

type ExecutionFeedProps = {
  events: SSEEvent[];
  assistantText: string;
};

function ExecutionFeed({ events, assistantText }: ExecutionFeedProps) {
  const visible = events.filter((e) => e.type !== "token");
  return (
    <Card className="p-4">
      <div className="mb-2 text-sm font-medium">執行紀錄</div>
      <div className="space-y-1 text-xs">
        {visible.map((event, idx) => (
          <FeedRow key={idx} event={event} />
        ))}
        {assistantText && (
          <div className="mt-3 rounded border bg-background p-3 text-sm">
            <div className="mb-1 text-xs text-muted-foreground">Bot 回覆</div>
            {assistantText}
          </div>
        )}
      </div>
    </Card>
  );
}

function FeedRow({ event }: { event: SSEEvent }) {
  const labels: Record<string, string> = {
    status: "🧠",
    tool_calls: "🔧",
    sources: "📚",
    contact: "👤",
    message_id: "🆔",
    conversation_id: "💬",
    done: "✅",
    error: "⚠️",
  };
  const icon = labels[event.type] ?? "·";

  let detail = "";
  if (event.type === "status" && typeof event.status === "string") {
    detail = event.status;
  } else if (event.type === "tool_calls" && Array.isArray(event.tool_calls)) {
    const names = (event.tool_calls as Array<{ tool_name: string }>)
      .map((c) => c.tool_name)
      .join(", ");
    detail = names;
  } else if (event.type === "sources" && Array.isArray(event.sources)) {
    detail = `${event.sources.length} chunks`;
  } else if (event.type === "done" && typeof event.trace_id === "string") {
    detail = `trace_id=${event.trace_id.slice(0, 8)}`;
  }

  return (
    <div className="flex gap-2 font-mono">
      <span>{icon}</span>
      <span className="text-muted-foreground">{event.type}</span>
      {detail && <span className="text-foreground/80">{detail}</span>}
    </div>
  );
}
