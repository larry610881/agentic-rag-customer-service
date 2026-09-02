import {
  Brain,
  Wrench,
  MessageCircle,
  Router,
  Users,
  User,
  ShieldAlert,
  Activity,
  ShieldCheck,
  Bot,
  MessagesSquare,
  History,
  Binary,
  Search,
  Database,
  Send,
} from "lucide-react";
import type { ExecutionNodeType } from "@/types/agent-trace";

// Tailwind colour pairs（border + bg）— light/dark 同步。
// admin 觀測頁的 trace graph 與 Studio canvas 共用這份配色，確保節點視覺語義一致。
export const NODE_COLORS: Record<ExecutionNodeType, string> = {
  user_input: "border-slate-400 bg-slate-50 dark:bg-slate-900",
  router: "border-amber-400 bg-amber-50 dark:bg-amber-950",
  meta_router: "border-amber-400 bg-amber-50 dark:bg-amber-950",
  supervisor_dispatch: "border-purple-400 bg-purple-50 dark:bg-purple-950",
  worker_routing: "border-purple-400 bg-purple-50 dark:bg-purple-950",
  agent_llm: "border-blue-400 bg-blue-50 dark:bg-blue-950",
  tool_call: "border-emerald-400 bg-emerald-50 dark:bg-emerald-950",
  tool_result: "border-emerald-400 bg-emerald-50 dark:bg-emerald-950",
  final_response: "border-green-400 bg-green-50 dark:bg-green-950",
  worker_execution: "border-indigo-400 bg-indigo-50 dark:bg-indigo-950",
  // Sprint A++: prompt guard blocks — 預設 orange（失敗時外層自動套 red variant）
  guard_input_blocked: "border-orange-500 bg-orange-50 dark:bg-orange-950",
  guard_output_blocked: "border-orange-500 bg-orange-50 dark:bg-orange-950",
  // Issue #57: wall-clock root 與非 agent 階段節點（時間軸視圖優先使用）
  request: "border-zinc-500 bg-zinc-100 dark:bg-zinc-800",
  webhook_verify: "border-teal-400 bg-teal-50 dark:bg-teal-950",
  bot_load: "border-sky-400 bg-sky-50 dark:bg-sky-950",
  conversation_load: "border-sky-400 bg-sky-50 dark:bg-sky-950",
  history_load: "border-sky-400 bg-sky-50 dark:bg-sky-950",
  embed_query: "border-cyan-400 bg-cyan-50 dark:bg-cyan-950",
  vector_search: "border-cyan-400 bg-cyan-50 dark:bg-cyan-950",
  persist: "border-stone-400 bg-stone-50 dark:bg-stone-900",
  reply_push: "border-lime-400 bg-lime-50 dark:bg-lime-950",
};

/** 未知 node_type（backend 新增但前端尚未登錄）的 fallback 配色 */
export const NODE_COLOR_FALLBACK =
  "border-gray-400 bg-gray-50 dark:bg-gray-900";

/** 以字串查配色，未知類型回 fallback — 給時間軸等不受 union 約束的視圖使用 */
export function nodeColorClass(nodeType: string): string {
  return (
    (NODE_COLORS as Record<string, string | undefined>)[nodeType] ??
    NODE_COLOR_FALLBACK
  );
}

export const NODE_ICONS: Record<ExecutionNodeType, React.ElementType> = {
  user_input: User,
  router: Router,
  meta_router: Router,
  supervisor_dispatch: Users,
  worker_routing: Router,
  agent_llm: Brain,
  tool_call: Wrench,
  tool_result: Wrench,
  final_response: MessageCircle,
  worker_execution: Users,
  guard_input_blocked: ShieldAlert,
  guard_output_blocked: ShieldAlert,
  request: Activity,
  webhook_verify: ShieldCheck,
  bot_load: Bot,
  conversation_load: MessagesSquare,
  history_load: History,
  embed_query: Binary,
  vector_search: Search,
  persist: Database,
  reply_push: Send,
};

// Phase 1: 失敗節點視覺 (outcome=="failed") — 一致紅色 variant 取代各 type 既有色
// + ping-once 一次性動畫吸引目光，不持續閃爍以免畫面躁動。
export const NODE_COLORS_FAILED =
  "border-red-500 bg-red-50 dark:bg-red-950 ring-1 ring-red-400/50";

export const PING_ONCE_CLASS = "studio-ping-once";

export function durationColor(ms: number): string {
  if (ms >= 2000) return "text-red-600 dark:text-red-400";
  if (ms >= 500) return "text-yellow-600 dark:text-yellow-400";
  return "text-green-600 dark:text-green-400";
}
