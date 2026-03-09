import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ProviderList } from "@/features/settings/components/provider-list";
import { ApiKeyList } from "@/features/settings/components/api-key-list";
import { SystemPromptEditor } from "@/features/settings/components/system-prompt-editor";
import { useAuthStore } from "@/stores/use-auth-store";

const tabs = [
  { value: "llm", label: "LLM" },
  { value: "api-key", label: "API Key" },
  { value: "prompts", label: "系統提示詞", adminOnly: true },
] as const;

export default function ProvidersSettingsPage() {
  const [activeTab, setActiveTab] = useState<string>("llm");
  const role = useAuthStore((s) => s.role);
  const isAdmin = role === "system_admin";

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">供應商設定</h1>
        <p className="text-muted-foreground">
          管理 LLM 供應商與 API Key。Embedding 統一使用 OpenAI
          text-embedding-3-small。
        </p>
      </div>

      <div className="flex gap-2 border-b pb-2">
        {tabs
          .filter((tab) => !tab.adminOnly || isAdmin)
          .map((tab) => (
            <Button
              key={tab.label}
              variant="ghost"
              size="sm"
              className={cn(
                activeTab === tab.value && "bg-muted font-semibold",
              )}
              onClick={() => setActiveTab(tab.value)}
            >
              {tab.label}
            </Button>
          ))}
      </div>

      {activeTab === "api-key" ? (
        <ApiKeyList />
      ) : activeTab === "prompts" ? (
        <SystemPromptEditor />
      ) : (
        <ProviderList />
      )}
    </div>
  );
}
