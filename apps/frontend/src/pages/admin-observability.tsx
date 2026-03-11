import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ObservabilityTracesTable } from "@/features/admin/components/observability-traces-table";
import { ObservabilityEvalsTable } from "@/features/admin/components/observability-evals-table";
import { DiagnosticRulesEditor } from "@/features/admin/components/diagnostic-rules-editor";

export default function AdminObservabilityPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">可觀測性</h1>
        <p className="text-muted-foreground">
          RAG 追蹤記錄與品質評估結果
        </p>
      </div>
      <Tabs defaultValue="traces">
        <TabsList>
          <TabsTrigger value="traces">RAG 追蹤</TabsTrigger>
          <TabsTrigger value="evals">品質評估</TabsTrigger>
          <TabsTrigger value="rules">診斷規則</TabsTrigger>
        </TabsList>
        <TabsContent value="traces" className="pt-4">
          <ObservabilityTracesTable />
        </TabsContent>
        <TabsContent value="evals" className="pt-4">
          <ObservabilityEvalsTable />
        </TabsContent>
        <TabsContent value="rules" className="pt-4">
          <DiagnosticRulesEditor />
        </TabsContent>
      </Tabs>
    </div>
  );
}
