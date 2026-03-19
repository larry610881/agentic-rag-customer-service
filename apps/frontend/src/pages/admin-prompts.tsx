import { SystemPromptEditor } from "@/features/settings/components/system-prompt-editor";

export default function AdminPromptsPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">系統提示詞</h1>
        <p className="text-muted-foreground">
          管理 AI Agent 的系統提示詞模板
        </p>
      </div>
      <SystemPromptEditor />
    </div>
  );
}
