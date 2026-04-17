import { useCallback, useMemo, useState } from "react";
import { Send, Sparkles } from "lucide-react";
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
import {
  BlueprintCanvas,
  blueprintToolNodeId,
  type BlueprintAgentSpec,
  type ChunkNodeSpec,
} from "./blueprint-canvas";
import type { Bot } from "@/types/bot";

type BotStudioCanvasProps = {
  bot: Bot;
};

const STREAM_RESET_LIMIT = 80;

/**
 * Bot Studio Canvas — Phase 1 升級版（真實對應）。
 *
 * 上半：BlueprintCanvas (ReactFlow) 顯示 main agent + workers + tools，
 *   stream events 帶 node_id 來精準點亮對應節點（取代 MVP 的字串啟發式）。
 * 中間：聊天輸入 + 演示模式 Switch。
 * 下半：執行紀錄 feed + 結束後完整 DAG。
 *
 * Phase 1 變更：
 *  - worker_routing event → 對應 worker 卡片點亮（不再是「全亮」）
 *  - sources event → 動態長出 chunk 子節點到 rag tool 下方
 *  - error event → 對應 node_id 紅框 + 一次性 ping 動畫
 */
export function BotStudioCanvas({ bot }: BotStudioCanvasProps) {
  const { data: workers = [] } = useWorkers(bot.id);
  const { data: builtInTools = [] } = useBuiltInTools();

  const [message, setMessage] = useState("");
  const [slowMode, setSlowMode] = useState(false);

  // Phase 1: 用 worker.name (BlueprintAgentSpec.id) 來追蹤啟用的 agent
  const [activeAgentIds, setActiveAgentIds] = useState<Set<string>>(new Set());
  // tool key = "{agentId}::{toolName}"
  const [activeToolKeys, setActiveToolKeys] = useState<Set<string>>(new Set());
  // failed node id = blueprint id ("agent:main" / "agent:{name}" / "tool:{agentId}:{toolName}")
  const [failedNodeIds, setFailedNodeIds] = useState<Set<string>>(new Set());
  const [errorMessages, setErrorMessages] = useState<Record<string, string>>({});
  const [chunkNodes, setChunkNodes] = useState<ChunkNodeSpec[]>([]);

  const [eventLog, setEventLog] = useState<SSEEvent[]>([]);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [assistantText, setAssistantText] = useState("");

  // 目前選中的 worker（worker_routing 後設定）— 該 worker 的 tools 要啟用
  const [selectedWorkerName, setSelectedWorkerName] = useState<string | null>(
    null,
  );

  const builtInToolByName = useMemo(() => {
    const m = new Map<string, { label: string }>();
    for (const t of builtInTools) m.set(t.name, { label: t.label });
    return m;
  }, [builtInTools]);

  const agents: BlueprintAgentSpec[] = useMemo(() => {
    const enrich = (n: string): string =>
      builtInToolByName.get(n)?.label ?? n;
    const main: BlueprintAgentSpec = {
      id: "main",
      label: bot.name || "Main Agent",
      isMain: true,
      toolNames: (bot.enabled_tools ?? []).map(enrich),
      metadata: {
        llm_provider: bot.llm_provider,
        llm_model: bot.llm_model,
        knowledge_base_count: bot.knowledge_base_ids?.length ?? 0,
      },
    };
    const workerNodes: BlueprintAgentSpec[] = workers.map((w) => ({
      id: w.name,
      label: w.name,
      isMain: false,
      toolNames: (w.enabled_tools ?? bot.enabled_tools ?? []).map(enrich),
      metadata: {
        llm_provider: w.llm_provider,
        llm_model: w.llm_model,
        knowledge_base_count: w.knowledge_base_ids?.length ?? 0,
        description: w.description,
      },
    }));
    return [main, ...workerNodes];
  }, [
    bot.name,
    bot.enabled_tools,
    bot.llm_provider,
    bot.llm_model,
    bot.knowledge_base_ids,
    workers,
    builtInToolByName,
  ]);

  // 目前的「執行中 agent」：worker_routing 選定 → 該 worker；未選 → main
  const currentAgentId = selectedWorkerName ?? "main";

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
        setActiveToolKeys((prev) => {
          const next = new Set(prev);
          for (const c of calls) {
            // 找對應 agent 的 tool（用 enrich 後的 label 對應）
            const enrichedName =
              builtInToolByName.get(c.tool_name)?.label ?? c.tool_name;
            next.add(`${currentAgentId}::${enrichedName}`);
          }
          return next;
        });
      }
    },
    onWorkerRouting: ({ worker_name }) => {
      setSelectedWorkerName(worker_name);
      setActiveAgentIds((prev) => new Set([...prev, worker_name]));
    },
    onChunkNode: (toolNodeId, source, idx) => {
      const newChunk: ChunkNodeSpec = {
        id: `${toolNodeId}::${idx}::${Date.now()}`,
        parentToolNodeId: toolNodeId,
        documentName:
          (typeof source.document_name === "string" && source.document_name) ||
          (typeof source.source === "string" && source.source) ||
          "chunk",
        score: typeof source.score === "number" ? source.score : 0,
        snippet:
          typeof source.content_snippet === "string"
            ? source.content_snippet.slice(0, 80)
            : "",
      };
      setChunkNodes((prev) => [...prev, newChunk]);
    },
    onFailedNode: ({ error_message }) => {
      // node_id 由 stream 提供 → 但藍圖節點 id 是 blueprint 命名（"agent:xx"），
      // Phase 1 失敗一般落在 current agent 上，標記 currentAgent。
      const targetId = `agent:${currentAgentId}`;
      setFailedNodeIds((prev) => new Set([...prev, targetId]));
      setErrorMessages((prev) => ({
        ...prev,
        [targetId]: error_message,
      }));
    },
    onTraceComplete: (id) => setTraceId(id),
    onError: (err) => {
      console.error("[Studio] streaming error:", err);
    },
  });

  const handleSend = useCallback(() => {
    if (!message.trim() || isStreaming) return;
    setActiveAgentIds(new Set(["main"]));
    setActiveToolKeys(new Set());
    setFailedNodeIds(new Set());
    setErrorMessages({});
    setChunkNodes([]);
    setEventLog([]);
    setTraceId(null);
    setAssistantText("");
    setSelectedWorkerName(null);
    void sendMessage({ message: message.trim(), botId: bot.id, slowMode });
    setMessage("");
  }, [message, isStreaming, sendMessage, bot.id, slowMode]);

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium">
          <Sparkles className="h-4 w-4 text-violet-500" />
          Bot 配置藍圖
          <span className="text-xs font-normal text-muted-foreground">
            {agents.length} agent · 對話開始後對應節點會點亮、失敗節點會紅框 ping
          </span>
        </div>
        <BlueprintCanvas
          agents={agents}
          activeAgentIds={activeAgentIds}
          activeToolKeys={activeToolKeys}
          failedNodeIds={failedNodeIds}
          errorMessages={errorMessages}
          chunkNodes={chunkNodes}
        />
      </Card>

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
              <code className="font-mono">
                {completedTrace.trace_id.slice(0, 8)}
              </code>
            </span>
          </div>
          <AgentTraceGraph execNodes={completedTrace.nodes} />
        </Card>
      )}
    </div>
  );
}

// 確保 blueprintToolNodeId import 不被 tree-shake 掉（給未來精準對應 tool 用）
void blueprintToolNodeId;

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
    worker_routing: "🎯",
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
  } else if (
    event.type === "worker_routing" &&
    typeof event.worker_name === "string"
  ) {
    detail = `→ ${event.worker_name}`;
  } else if (event.type === "done" && typeof event.trace_id === "string") {
    detail = `trace_id=${event.trace_id.slice(0, 8)}`;
  } else if (event.type === "error" && typeof event.message === "string") {
    detail = event.message;
  }

  const tsBadge =
    typeof event.ts_ms === "number" && event.ts_ms > 0
      ? ` ${event.ts_ms.toFixed(0)}ms`
      : "";

  return (
    <div className="flex gap-2 font-mono">
      <span>{icon}</span>
      <span className="text-muted-foreground">{event.type}</span>
      {detail && <span className="text-foreground/80 truncate">{detail}</span>}
      {tsBadge && (
        <span className="ml-auto text-muted-foreground/60">{tsBadge}</span>
      )}
    </div>
  );
}
