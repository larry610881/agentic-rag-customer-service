import { useMemo, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ObservabilityEvalsTable } from "@/features/admin/components/observability-evals-table";
import { AgentTracesTable } from "@/features/admin/components/agent-traces-table";
import { AgentTracesGroupedTable } from "@/features/admin/components/agent-traces-grouped-table";
import { AgentTraceDetail } from "@/features/admin/components/agent-trace-detail";
import {
  AgentTracesFilterRow,
  daysToDateFrom,
  useAgentTracesFilterUrl,
} from "@/features/admin/components/agent-traces-filter-row";
import type { AgentTraceFilters } from "@/hooks/queries/use-agent-traces";
import type { AgentExecutionTrace } from "@/types/agent-trace";

export default function AdminObservabilityPage() {
  const [selectedTrace, setSelectedTrace] =
    useState<AgentExecutionTrace | null>(null);
  const [filterValue, setFilterValue] = useAgentTracesFilterUrl();

  /** filter row 狀態 → hook 接受的 AgentTraceFilters */
  const apiFilters: Omit<AgentTraceFilters, "limit" | "offset"> = useMemo(
    () => ({
      tenant_id: filterValue.tenant_id,
      bot_id: filterValue.bot_id,
      source: filterValue.source,
      agent_mode: filterValue.agent_mode,
      outcome: filterValue.outcome,
      min_total_ms: filterValue.min_total_ms,
      max_total_ms: filterValue.max_total_ms,
      min_total_tokens: filterValue.min_total_tokens,
      max_total_tokens: filterValue.max_total_tokens,
      keyword: filterValue.keyword,
      date_from: daysToDateFrom(filterValue.days),
    }),
    [filterValue],
  );

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">可觀測性</h1>
        <p className="text-muted-foreground">Agent 執行追蹤與品質評估</p>
      </div>
      <Tabs defaultValue="agent-traces">
        <TabsList>
          <TabsTrigger value="agent-traces">Agent 執行追蹤</TabsTrigger>
          <TabsTrigger value="evals">品質評估</TabsTrigger>
        </TabsList>
        <TabsContent value="agent-traces" className="pt-4 space-y-4">
          {selectedTrace ? (
            <AgentTraceDetail
              trace={selectedTrace}
              onBack={() => setSelectedTrace(null)}
            />
          ) : (
            <>
              <AgentTracesFilterRow
                value={filterValue}
                onChange={setFilterValue}
              />
              {filterValue.view === "grouped" ? (
                <AgentTracesGroupedTable
                  filters={apiFilters}
                  onSelectTrace={setSelectedTrace}
                />
              ) : (
                <AgentTracesTable
                  filters={apiFilters}
                  onSelectTrace={setSelectedTrace}
                />
              )}
            </>
          )}
        </TabsContent>
        <TabsContent value="evals" className="pt-4">
          <ObservabilityEvalsTable />
        </TabsContent>
      </Tabs>
    </div>
  );
}
