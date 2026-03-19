import { DiagnosticRulesEditor } from "@/features/admin/components/diagnostic-rules-editor";

export default function AdminDiagnosticRulesPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">診斷規則</h1>
        <p className="text-muted-foreground">
          管理 RAG 品質診斷規則與告警閾值
        </p>
      </div>
      <DiagnosticRulesEditor />
    </div>
  );
}
