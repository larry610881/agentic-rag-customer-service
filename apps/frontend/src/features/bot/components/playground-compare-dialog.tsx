/** Issue #54 §15 — 儲存前對照測試 Playground：
 * 一次輸入同時發「線上版 vs 草稿」兩個影子對話（test_mode，六面隔離），
 * 每則回應可展開執行軌跡 DAG。token 消耗計入租戶（分類：playground）。
 */

import { useEffect, useRef, useState } from "react";
import { FlaskConical, Loader2, Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { AgentTraceGraph } from "@/features/admin/components/agent-trace-graph";
import { API_BASE } from "@/lib/api-config";
import { fetchSSE, type SSEEvent } from "@/lib/sse-client";
import { useAuthStore } from "@/stores/use-auth-store";
import type { ExecutionNode } from "@/types/agent-trace";

interface PlaygroundTurn {
  role: "user" | "assistant";
  content: string;
  traceNodes?: ExecutionNode[];
  latencyMs?: number;
}

interface ColumnState {
  turns: PlaygroundTurn[];
  streaming: boolean;
}

const EMPTY_COLUMN: ColumnState = { turns: [], streaming: false };

function TurnBubble({ turn }: { turn: PlaygroundTurn }) {
  const [showTrace, setShowTrace] = useState(false);
  const isUser = turn.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          isUser
            ? "max-w-[85%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
            : "max-w-[85%] rounded-lg bg-muted px-3 py-2 text-sm"
        }
      >
        <p className="whitespace-pre-wrap">{turn.content || "…"}</p>
        {!isUser && turn.traceNodes && turn.traceNodes.length > 0 && (
          <div className="mt-1">
            <button
              type="button"
              className="text-[11px] text-primary underline-offset-2 hover:underline"
              onClick={() => setShowTrace((v) => !v)}
            >
              {showTrace ? "收合執行軌跡" : "執行軌跡 DAG"}
              {turn.latencyMs != null ? `（${turn.latencyMs}ms）` : ""}
            </button>
            {showTrace && (
              <div className="mt-1 h-56 w-[60vw] max-w-full rounded border bg-background">
                <AgentTraceGraph execNodes={turn.traceNodes} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CompareColumn({
  title
  ,
  badge,
  column,
}: {
  title: string;
  badge?: string;
  column: ColumnState;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  // L18：串流時跟隨捲到底（對照 message-list.tsx 同模式），否則對話超過欄高後
  // 新 token 一直長在可視範圍外，每輪需手動捲動兩個欄位
  const lastContent =
    column.turns.length > 0
      ? column.turns[column.turns.length - 1].content
      : "";
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [lastContent, column.turns.length]);
  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-lg border">
      <div className="flex items-center gap-2 border-b px-3 py-2 text-sm font-medium">
        {title}
        {badge && <Badge variant="outline">{badge}</Badge>}
        {column.streaming && <Loader2 className="h-3 w-3 animate-spin" />}
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {column.turns.length === 0 && (
          <p className="text-xs text-muted-foreground">
            輸入訊息後，兩版回應會並排顯示。
          </p>
        )}
        {column.turns.map((t, i) => (
          <TurnBubble key={i} turn={t} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

interface PlaygroundCompareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  botId: string;
  /** 草稿設定（受版控欄位的候選值，如 { base_prompt, bot_prompt, llm_params } ） */
  draftOverride: Record<string, unknown>;
}

export function PlaygroundCompareDialog({
  open,
  onOpenChange,
  botId,
  draftOverride,
}: PlaygroundCompareDialogProps) {
  const token = useAuthStore((s) => s.token);
  const [message, setMessage] = useState("");
  const [left, setLeft] = useState<ColumnState>(EMPTY_COLUMN);
  const [right, setRight] = useState<ColumnState>(EMPTY_COLUMN);

  const busy = left.streaming || right.streaming;

  const runColumn = async (
    setColumn: React.Dispatch<React.SetStateAction<ColumnState>>,
    history: PlaygroundTurn[],
    text: string,
    override: Record<string, unknown> | null,
  ) => {
    setColumn((prev) => ({
      streaming: true,
      turns: [
        ...prev.turns,
        { role: "user", content: text },
        { role: "assistant", content: "" },
      ],
    }));
    const updateLast = (fn: (t: PlaygroundTurn) => PlaygroundTurn) =>
      setColumn((prev) => ({
        ...prev,
        turns: prev.turns.map((t, i) =>
          i === prev.turns.length - 1 ? fn(t) : t,
        ),
      }));

    const start = performance.now();
    try {
      await fetchSSE(
        `${API_BASE}/api/v1/agent/chat/stream`,
        {
          message: text,
          bot_id: botId,
          test_mode: true,
          ...(override ? { config_override: override } : {}),
          history_override: history.map((t) => ({
            role: t.role,
            content: t.content,
          })),
        },
        token ?? "",
        (event: SSEEvent) => {
          if (event.type === "token") {
            updateLast((t) => ({
              ...t,
              content: t.content + String(event.content ?? ""),
            }));
          }
          if (event.type === "done") {
            updateLast((t) => ({
              ...t,
              traceNodes:
                (event.trace_nodes as ExecutionNode[] | undefined) ?? undefined,
              latencyMs: Math.round(performance.now() - start),
            }));
          }
        },
        () => {
          updateLast((t) => ({
            ...t,
            content: t.content || "（串流中斷）",
          }));
        },
        { "X-Usage-Category": "playground" },
      );
    } catch {
      updateLast((t) => ({ ...t, content: t.content || "（請求失敗）" }));
    } finally {
      setColumn((prev) => ({ ...prev, streaming: false }));
    }
  };

  const handleSend = () => {
    const text = message.trim();
    if (!text || busy) return;
    setMessage("");
    // 兩欄各自延續自己的脈絡（回答不同導致分岔是預期行為）
    void runColumn(setLeft, left.turns, text, null);
    void runColumn(setRight, right.turns, text, draftOverride);
  };

  const handleReset = () => {
    setLeft(EMPTY_COLUMN);
    setRight(EMPTY_COLUMN);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-w-6xl flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            對照測試：線上版 vs 草稿
            <span className="text-xs font-normal text-muted-foreground">
              測試對話不落庫、不影響線上；消耗 token 計入用量（分類：對照測試）
            </span>
          </DialogTitle>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 gap-3">
          <CompareColumn title="線上版" column={left} />
          <CompareColumn title="草稿" badge="draft" column={right} />
        </div>
        <div className="flex items-end gap-2 border-t pt-3">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            rows={2}
            placeholder="輸入訊息，同時發給兩版（Enter 送出 / Shift+Enter 換行）"
            className="flex-1"
          />
          <div className="flex flex-col gap-1">
            <Button size="sm" disabled={busy || !message.trim()} onClick={handleSend}>
              <Send className="mr-1 h-4 w-4" />
              送出
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={handleReset}>
              清空
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
