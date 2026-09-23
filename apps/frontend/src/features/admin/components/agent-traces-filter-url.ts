import { useSearchParams } from "react-router-dom";
import type { TraceOutcome } from "@/types/agent-trace";

/**
 * S-Gov.6a: Agent Trace filter 值與 URL search params 的雙向轉換
 *（自 agent-traces-filter-row.tsx 抽出，讓元件檔只匯出元件以支援 Fast Refresh）
 *
 * URL params 例：?days=7&tenant_id=...&source=line&outcome=failed&keyword=退貨&view=grouped
 */

export type AgentTracesFilterValue = {
  days: number; // 0 = 全部
  tenant_id?: string;
  bot_id?: string;
  source?: string;
  agent_mode?: string;
  outcome?: TraceOutcome;
  min_total_ms?: number;
  max_total_ms?: number;
  min_total_tokens?: number;
  max_total_tokens?: number;
  keyword?: string;
  view: "flat" | "grouped";
};

export const AGENT_TRACES_FILTER_DEFAULTS: AgentTracesFilterValue = { days: 30, view: "flat" };

function readParams(sp: URLSearchParams): AgentTracesFilterValue {
  const days = Number(sp.get("days") ?? "30");
  return {
    days: Number.isNaN(days) ? 30 : days,
    tenant_id: sp.get("tenant_id") ?? undefined,
    bot_id: sp.get("bot_id") ?? undefined,
    source: sp.get("source") ?? undefined,
    agent_mode: sp.get("agent_mode") ?? undefined,
    outcome: (sp.get("outcome") as TraceOutcome | null) ?? undefined,
    min_total_ms: sp.get("min_total_ms")
      ? Number(sp.get("min_total_ms"))
      : undefined,
    max_total_ms: sp.get("max_total_ms")
      ? Number(sp.get("max_total_ms"))
      : undefined,
    min_total_tokens: sp.get("min_total_tokens")
      ? Number(sp.get("min_total_tokens"))
      : undefined,
    max_total_tokens: sp.get("max_total_tokens")
      ? Number(sp.get("max_total_tokens"))
      : undefined,
    keyword: sp.get("keyword") ?? undefined,
    view: (sp.get("view") as "flat" | "grouped" | null) === "grouped"
      ? "grouped"
      : "flat",
  };
}

function writeParams(value: AgentTracesFilterValue): URLSearchParams {
  const sp = new URLSearchParams();
  if (value.days !== 30) sp.set("days", String(value.days));
  if (value.tenant_id) sp.set("tenant_id", value.tenant_id);
  if (value.bot_id) sp.set("bot_id", value.bot_id);
  if (value.source) sp.set("source", value.source);
  if (value.agent_mode) sp.set("agent_mode", value.agent_mode);
  if (value.outcome) sp.set("outcome", value.outcome);
  if (value.min_total_ms !== undefined)
    sp.set("min_total_ms", String(value.min_total_ms));
  if (value.max_total_ms !== undefined)
    sp.set("max_total_ms", String(value.max_total_ms));
  if (value.min_total_tokens !== undefined)
    sp.set("min_total_tokens", String(value.min_total_tokens));
  if (value.max_total_tokens !== undefined)
    sp.set("max_total_tokens", String(value.max_total_tokens));
  if (value.keyword) sp.set("keyword", value.keyword);
  if (value.view === "grouped") sp.set("view", "grouped");
  return sp;
}

/** 日期 preset 換算成 date_from ISO8601；0 = undefined（全部）。 */
export function daysToDateFrom(days: number): string | undefined {
  if (!days || days <= 0) return undefined;
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString();
}

/**
 * URL search params ↔ filter value 雙向 sync hook。
 * 點 row 跳到詳情頁返回後，filter 仍保留；URL 可直接複製分享。
 */
export function useAgentTracesFilterUrl(): [
  AgentTracesFilterValue,
  (v: AgentTracesFilterValue) => void,
] {
  const [searchParams, setSearchParams] = useSearchParams();
  const value = readParams(searchParams);
  const setValue = (v: AgentTracesFilterValue) => {
    setSearchParams(writeParams(v), { replace: true });
  };
  return [value, setValue];
}
