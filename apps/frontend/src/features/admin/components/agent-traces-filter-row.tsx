import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronRight, Search, X } from "lucide-react";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { AdminBotFilter } from "@/features/admin/components/admin-bot-filter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { TraceOutcome } from "@/types/agent-trace";

/**
 * S-Gov.6a: Agent Trace Filter Row（含 URL ↔ state 雙向 sync）
 *
 * Row 1: 日期預設 / 租戶 / Bot / Source / Mode
 * Row 2: Outcome / View toggle (flat vs grouped)
 * Row 3: 進階摺疊 — 耗時範圍 / Token 範圍 / 關鍵字
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

const DEFAULTS: AgentTracesFilterValue = { days: 30, view: "flat" };

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

interface FilterRowProps {
  value: AgentTracesFilterValue;
  onChange: (value: AgentTracesFilterValue) => void;
}

export function AgentTracesFilterRow({ value, onChange }: FilterRowProps) {
  const [advancedOpen, setAdvancedOpen] = useState(
    Boolean(
      value.min_total_ms ||
        value.max_total_ms ||
        value.min_total_tokens ||
        value.max_total_tokens ||
        value.keyword,
    ),
  );

  const update = (patch: Partial<AgentTracesFilterValue>) =>
    onChange({ ...value, ...patch });

  const reset = () => onChange(DEFAULTS);

  return (
    <div className="flex flex-col gap-3">
      {/* Row 1: 常用 filter */}
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={String(value.days)}
          onValueChange={(v) => update({ days: Number(v) })}
        >
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">全部時間</SelectItem>
            <SelectItem value="1">過去 1 天</SelectItem>
            <SelectItem value="7">過去 7 天</SelectItem>
            <SelectItem value="30">過去 30 天</SelectItem>
            <SelectItem value="90">過去 90 天</SelectItem>
          </SelectContent>
        </Select>

        <AdminTenantFilter
          value={value.tenant_id}
          onChange={(v) => update({ tenant_id: v, bot_id: undefined })}
        />
        <AdminBotFilter
          value={value.bot_id}
          onChange={(v) => update({ bot_id: v })}
          tenantId={value.tenant_id}
        />

        <Select
          value={value.source ?? "all"}
          onValueChange={(v) =>
            update({ source: v === "all" ? undefined : v })
          }
        >
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="來源" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部來源</SelectItem>
            <SelectItem value="web">Web</SelectItem>
            <SelectItem value="widget">Widget</SelectItem>
            <SelectItem value="line">LINE</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={value.agent_mode ?? "all"}
          onValueChange={(v) =>
            update({ agent_mode: v === "all" ? undefined : v })
          }
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Agent 模式" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部模式</SelectItem>
            <SelectItem value="react">ReAct</SelectItem>
            <SelectItem value="supervisor">Supervisor</SelectItem>
            <SelectItem value="meta_supervisor">Meta Supervisor</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Row 2: 狀態 + view toggle */}
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={value.outcome ?? "all"}
          onValueChange={(v) =>
            update({
              outcome: v === "all" ? undefined : (v as TraceOutcome),
            })
          }
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Outcome" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部 Outcome</SelectItem>
            <SelectItem value="success">✅ Success</SelectItem>
            <SelectItem value="failed">❌ Failed</SelectItem>
            <SelectItem value="partial">⚠️ Partial</SelectItem>
          </SelectContent>
        </Select>

        <ToggleGroup
          type="single"
          value={value.view}
          onValueChange={(v) =>
            v && update({ view: v as "flat" | "grouped" })
          }
          className="border rounded-md"
        >
          <ToggleGroupItem value="flat" className="px-3 text-xs">
            單筆 Trace
          </ToggleGroupItem>
          <ToggleGroupItem value="grouped" className="px-3 text-xs">
            依對話聚合
          </ToggleGroupItem>
        </ToggleGroup>

        <Button
          variant="ghost"
          size="sm"
          className="ml-auto text-muted-foreground"
          onClick={reset}
        >
          <X className="h-3.5 w-3.5 mr-1" />
          重設 filter
        </Button>
      </div>

      {/* Row 3: 進階（摺疊）*/}
      <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {advancedOpen ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            進階 filter（耗時 / Token 範圍 / 關鍵字）
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-3">
          <div className="flex flex-wrap items-end gap-4 rounded-md border bg-muted/20 p-3">
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-muted-foreground">耗時 (ms)</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={0}
                  placeholder="min"
                  value={value.min_total_ms ?? ""}
                  onChange={(e) =>
                    update({
                      min_total_ms:
                        e.target.value === ""
                          ? undefined
                          : Number(e.target.value),
                    })
                  }
                  className="w-[100px]"
                />
                <span className="text-muted-foreground">~</span>
                <Input
                  type="number"
                  min={0}
                  placeholder="max"
                  value={value.max_total_ms ?? ""}
                  onChange={(e) =>
                    update({
                      max_total_ms:
                        e.target.value === ""
                          ? undefined
                          : Number(e.target.value),
                    })
                  }
                  className="w-[100px]"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <Label className="text-xs text-muted-foreground">Token</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={0}
                  placeholder="min"
                  value={value.min_total_tokens ?? ""}
                  onChange={(e) =>
                    update({
                      min_total_tokens:
                        e.target.value === ""
                          ? undefined
                          : Number(e.target.value),
                    })
                  }
                  className="w-[100px]"
                />
                <span className="text-muted-foreground">~</span>
                <Input
                  type="number"
                  min={0}
                  placeholder="max"
                  value={value.max_total_tokens ?? ""}
                  onChange={(e) =>
                    update({
                      max_total_tokens:
                        e.target.value === ""
                          ? undefined
                          : Number(e.target.value),
                    })
                  }
                  className="w-[100px]"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
              <Label className="text-xs text-muted-foreground">關鍵字</Label>
              <div className="relative">
                <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="搜 nodes 內容（user_input / final_response）"
                  value={value.keyword ?? ""}
                  onChange={(e) =>
                    update({
                      keyword:
                        e.target.value === "" ? undefined : e.target.value,
                    })
                  }
                  className="pl-8"
                />
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
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
