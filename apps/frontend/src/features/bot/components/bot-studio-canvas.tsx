import { useCallback, useMemo, useRef, useState, useEffect } from "react";
import { Send, Sparkles, Eraser, Bot as BotIcon, User as UserIcon } from "lucide-react";
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
  type BlueprintAgentSpec,
  type ChunkNodeSpec,
} from "./blueprint-canvas";
import type { Bot } from "@/types/bot";
import { cn } from "@/lib/utils";

type BotStudioWorkspaceProps = {
  bot: Bot;
};

const STREAM_RESET_LIMIT = 80;

type ChatTurn = {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming: boolean;
  traceId?: string;
};

/**
 * Bot Studio Workspace — 獨立頁面 2-column layout：
 *  左：StudioDashboard（藍圖 + 執行紀錄 + 完整 DAG）
 *  右：StudioChatPanel（多輪對話 + slowMode + 清除按鈕）
 *
 * Phase 1 升級已完成（commit c4d78a0），本檔負責新版 layout 與多輪對話狀態管理。
 *
 * 多輪：保留 conversationId 跨 turn，每輪重置 lit/failed/chunks 但保留 chat history。
 */
export function BotStudioWorkspace({ bot }: BotStudioWorkspaceProps) {
  const { data: workers = [] } = useWorkers(bot.id);
  const { data: builtInTools = [] } = useBuiltInTools();

  const [slowMode, setSlowMode] = useState(false);

  // 多輪對話狀態
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const assistantTurnIdRef = useRef<string | null>(null);

  // 藍圖狀態（每輪重置）
  const [activeAgentIds, setActiveAgentIds] = useState<Set<string>>(new Set());
  const [activeToolKeys, setActiveToolKeys] = useState<Set<string>>(new Set());
  const [failedNodeIds, setFailedNodeIds] = useState<Set<string>>(new Set());
  const [errorMessages, setErrorMessages] = useState<Record<string, string>>({});
  const [chunkNodes, setChunkNodes] = useState<ChunkNodeSpec[]>([]);

  // 執行紀錄（每輪重置）
  const [eventLog, setEventLog] = useState<SSEEvent[]>([]);
  const [traceId, setTraceId] = useState<string | null>(null);

  // Refs 用來繞過 useStudioStreaming callbacks 的 closure 陷阱：
  // sendMessage 被呼叫時 callbacks 內的 currentAgentId 會被「凍結」為當下值，
  // 之後 setState re-render 不會更新 stream 內的舊 closure。
  // 改用 ref → 每次 stream event 都讀最新值。
  const currentAgentIdRef = useRef<string>("main");
  // Stream 收到 tool_calls 時記下對應的 BlueprintCanvas tool node id，
  // 之後 sources event 進來才能把 chunk 子節點掛到對的 tool 下面。
  const lastToolBlueprintIdRef = useRef<string | null>(null);

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

  const { data: completedTrace } = useAgentTraceDetail(traceId);

  const appendAssistantContent = useCallback((delta: string) => {
    setTurns((prev) => {
      const id = assistantTurnIdRef.current;
      if (!id) return prev;
      return prev.map((t) =>
        t.id === id ? { ...t, content: t.content + delta } : t,
      );
    });
  }, []);

  const finalizeAssistantTurn = useCallback((tid?: string) => {
    setTurns((prev) => {
      const id = assistantTurnIdRef.current;
      if (!id) return prev;
      return prev.map((t) =>
        t.id === id ? { ...t, isStreaming: false, traceId: tid } : t,
      );
    });
    assistantTurnIdRef.current = null;
  }, []);

  const { sendMessage, isStreaming } = useStudioStreaming({
    onEvent: (event) => {
      setEventLog((prev) =>
        prev.length >= STREAM_RESET_LIMIT ? prev : [...prev, event],
      );
      if (event.type === "token" && typeof event.content === "string") {
        appendAssistantContent(event.content);
      }
      if (event.type === "tool_calls" && Array.isArray(event.tool_calls)) {
        const calls = event.tool_calls as Array<{ tool_name: string }>;
        // 從 ref 讀「最新」當前 agent，避開 useStudioStreaming callbacks closure 凍結問題
        const agentId = currentAgentIdRef.current;
        setActiveToolKeys((prev) => {
          const next = new Set(prev);
          for (const c of calls) {
            const enrichedName =
              builtInToolByName.get(c.tool_name)?.label ?? c.tool_name;
            next.add(`${agentId}::${enrichedName}`);
          }
          return next;
        });
        // 記下對應的 BlueprintCanvas tool node id，給接下來 sources event 的 chunk 子節點掛載
        if (calls.length > 0) {
          const first = calls[0];
          const enrichedName =
            builtInToolByName.get(first.tool_name)?.label ?? first.tool_name;
          lastToolBlueprintIdRef.current = `tool:${agentId}:${enrichedName}`;
        }
      }
      if (
        event.type === "conversation_id" &&
        typeof event.conversation_id === "string"
      ) {
        setConversationId(event.conversation_id);
      }
    },
    onWorkerRouting: ({ worker_name }) => {
      // 同步更新 ref 讓接下來 stream callbacks 讀到最新 agent
      currentAgentIdRef.current = worker_name;
      // 替換語意：main 自動消失、選定 worker 點亮
      setActiveAgentIds(new Set([worker_name]));
      // main 上殘留的 tool 點亮也清掉（避免「跨 agent 點亮錯位」）
      setActiveToolKeys(new Set());
      // routing 後重置 lastTool，等 worker 真的呼叫 tool 才指派 parent
      lastToolBlueprintIdRef.current = null;
    },
    onChunkNode: (_unusedBackendUuid, source, idx) => {
      // hook 傳的 toolNodeId 是後端 trace UUID（不是 BlueprintCanvas node id）；
      // 改用 ref 中記下的 BlueprintCanvas tool node id 才能正確掛在對應 tool 下面
      const parentId = lastToolBlueprintIdRef.current;
      if (!parentId) return;
      const newChunk: ChunkNodeSpec = {
        id: `${parentId}::${idx}::${Date.now()}`,
        parentToolNodeId: parentId,
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
      // 從 ref 讀「真正當前」的 agent，不用 closure 凍結值
      const targetId = `agent:${currentAgentIdRef.current}`;
      setFailedNodeIds((prev) => new Set([...prev, targetId]));
      setErrorMessages((prev) => ({
        ...prev,
        [targetId]: error_message,
      }));
      // 失敗時也要把 assistant turn 收尾（不是 streaming）
      appendAssistantContent(`⚠️ ${error_message}`);
    },
    onTraceComplete: (id) => {
      setTraceId(id);
      finalizeAssistantTurn(id);
    },
    onError: (err) => {
      console.error("[Studio] streaming error:", err);
      finalizeAssistantTurn();
    },
  });

  const handleSend = useCallback(
    (message: string) => {
      if (!message.trim() || isStreaming) return;

      // 加 user turn + assistant turn (streaming)
      const userId = `u-${Date.now()}`;
      const assistantId = `a-${Date.now() + 1}`;
      assistantTurnIdRef.current = assistantId;
      setTurns((prev) => [
        ...prev,
        { id: userId, role: "user", content: message.trim(), isStreaming: false },
        { id: assistantId, role: "assistant", content: "", isStreaming: true },
      ]);

      // 重置藍圖 / chunks / 執行紀錄（保留 chat history）
      setActiveAgentIds(new Set(["main"]));
      setActiveToolKeys(new Set());
      setFailedNodeIds(new Set());
      setErrorMessages({});
      setChunkNodes([]);
      setEventLog([]);
      setTraceId(null);
      // refs 同步重置（避免上一輪遺留的 worker 名 / tool id 影響本輪 closure-bypass 邏輯）
      currentAgentIdRef.current = "main";
      lastToolBlueprintIdRef.current = null;

      void sendMessage({
        message: message.trim(),
        botId: bot.id,
        conversationId,
        slowMode,
      });
    },
    [isStreaming, sendMessage, bot.id, conversationId, slowMode],
  );

  const handleClearConversation = useCallback(() => {
    if (isStreaming) return;
    setTurns([]);
    setConversationId(null);
    setActiveAgentIds(new Set());
    setActiveToolKeys(new Set());
    setFailedNodeIds(new Set());
    setErrorMessages({});
    setChunkNodes([]);
    setEventLog([]);
    setTraceId(null);
    assistantTurnIdRef.current = null;
    currentAgentIdRef.current = "main";
    lastToolBlueprintIdRef.current = null;
  }, [isStreaming]);

  return (
    <div className="grid h-full grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
      {/* 左：儀表板 */}
      <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto pr-1">
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

        {eventLog.length > 0 && <ExecutionFeed events={eventLog} />}

        {completedTrace && (
          <Card className="p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-4 w-4 text-violet-500" />
              本輪執行 DAG
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

      {/* 右：對話 */}
      <StudioChatPanel
        turns={turns}
        isStreaming={isStreaming}
        slowMode={slowMode}
        onSlowModeChange={setSlowMode}
        onSend={handleSend}
        onClear={handleClearConversation}
        conversationId={conversationId}
      />
    </div>
  );
}

// 向後相容 alias — 既有匯入名（若 BotDetailForm 還用 BotStudioCanvas）
export const BotStudioCanvas = BotStudioWorkspace;

type StudioChatPanelProps = {
  turns: ChatTurn[];
  isStreaming: boolean;
  slowMode: boolean;
  onSlowModeChange: (v: boolean) => void;
  onSend: (message: string) => void;
  onClear: () => void;
  conversationId: string | null;
};

function StudioChatPanel({
  turns,
  isStreaming,
  slowMode,
  onSlowModeChange,
  onSend,
  onClear,
  conversationId,
}: StudioChatPanelProps) {
  const [message, setMessage] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 新訊息進來時自動捲到底
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

  const handleSubmit = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setMessage("");
  }, [message, isStreaming, onSend]);

  return (
    <Card className="flex h-full min-h-0 flex-col p-0">
      {/* Header */}
      <div className="flex items-center gap-2 border-b p-3">
        <BotIcon className="h-4 w-4 text-violet-500" />
        <span className="text-sm font-medium">試運轉對話</span>
        {conversationId && (
          <span className="text-xs text-muted-foreground">
            轉 #{conversationId.slice(0, 6)}
          </span>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          disabled={isStreaming || turns.length === 0}
          className="ml-auto"
          aria-label="清除對話"
        >
          <Eraser className="mr-1 h-3.5 w-3.5" />
          清除
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 min-h-0 space-y-3 overflow-y-auto p-4">
        {turns.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted-foreground">
            <Sparkles className="mb-2 h-6 w-6 text-violet-400" />
            送出第一則訊息開始試運轉
            <span className="mt-1 text-xs">
              觀察左側藍圖會跟著點亮、失敗會紅框 ping
            </span>
          </div>
        )}
        {turns.map((turn) => (
          <ChatBubble key={turn.id} turn={turn} />
        ))}
      </div>

      {/* Input + slowMode */}
      <div className="border-t p-3">
        <div className="mb-2 flex items-center gap-2">
          <Switch
            id="studio-slow-mode"
            checked={slowMode}
            onCheckedChange={onSlowModeChange}
            disabled={isStreaming}
          />
          <Label
            htmlFor="studio-slow-mode"
            className="cursor-pointer text-xs text-muted-foreground"
          >
            演示模式（每事件間隔 800ms）
          </Label>
        </div>
        <div className="flex items-end gap-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="輸入測試訊息（例：你好 / 查產品 / 退貨流程）"
            disabled={isStreaming}
            className="flex-1"
          />
          <Button
            onClick={handleSubmit}
            disabled={isStreaming || !message.trim()}
          >
            <Send className="mr-1 h-4 w-4" />
            送出
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ChatBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";
  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-900">
          <BotIcon className="h-4 w-4 text-violet-600 dark:text-violet-300" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[78%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap break-words",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted",
          turn.isStreaming && !turn.content && "italic opacity-60",
        )}
      >
        {turn.content || (turn.isStreaming ? "思考中..." : "")}
      </div>
      {isUser && (
        <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
          <UserIcon className="h-4 w-4 text-primary" />
        </div>
      )}
    </div>
  );
}

type ExecutionFeedProps = {
  events: SSEEvent[];
};

function ExecutionFeed({ events }: ExecutionFeedProps) {
  const visible = events.filter((e) => e.type !== "token");
  return (
    <Card className="p-3">
      <div className="mb-1 text-xs font-medium text-muted-foreground">
        執行紀錄
      </div>
      <div className="max-h-[160px] space-y-0.5 overflow-y-auto text-xs">
        {visible.map((event, idx) => (
          <FeedRow key={idx} event={event} />
        ))}
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
