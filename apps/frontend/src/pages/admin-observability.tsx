import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ObservabilityTracesTable } from "@/features/admin/components/observability-traces-table";
import { ObservabilityEvalsTable } from "@/features/admin/components/observability-evals-table";
import { AgentTracesTable } from "@/features/admin/components/agent-traces-table";
import { AgentTraceDetail } from "@/features/admin/components/agent-trace-detail";
import type { AgentExecutionTrace } from "@/types/agent-trace";

export default function AdminObservabilityPage() {
  const [selectedTrace, setSelectedTrace] =
    useState<AgentExecutionTrace | null>(null);

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">可觀測性</h1>
        <p className="text-muted-foreground">
          RAG 追蹤記錄、品質評估與 Agent 執行追蹤
        </p>
      </div>
      <Tabs defaultValue="traces">
        <TabsList>
          <TabsTrigger value="traces">RAG 追蹤</TabsTrigger>
          <TabsTrigger value="evals">品質評估</TabsTrigger>
          <TabsTrigger value="agent-traces">Agent 執行追蹤</TabsTrigger>
        </TabsList>
        <TabsContent value="traces" className="pt-4">
          <ObservabilityTracesTable />
        </TabsContent>
        <TabsContent value="evals" className="pt-4">
          <ObservabilityEvalsTable />
        </TabsContent>
        <TabsContent value="agent-traces" className="pt-4">
          {selectedTrace ? (
            <AgentTraceDetail
              trace={selectedTrace}
              onBack={() => setSelectedTrace(null)}
            />
          ) : (
            <AgentTracesTable onSelectTrace={setSelectedTrace} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
