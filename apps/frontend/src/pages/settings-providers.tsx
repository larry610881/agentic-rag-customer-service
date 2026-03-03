import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ProviderList } from "@/features/settings/components/provider-list";
import { ApiKeyList } from "@/features/settings/components/api-key-list";

const tabs = [
  { value: "llm", label: "LLM" },
  { value: "embedding", label: "Embedding" },
  { value: "api-key", label: "API Key" },
] as const;

export default function ProvidersSettingsPage() {
  const [activeTab, setActiveTab] = useState<string>("llm");

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">供應商設定</h1>
        <p className="text-muted-foreground">
          管理 LLM / Embedding 供應商與 API Key。
        </p>
      </div>

      <div className="flex gap-2 border-b pb-2">
        {tabs.map((tab) => (
          <Button
            key={tab.label}
            variant="ghost"
            size="sm"
            className={cn(
              activeTab === tab.value &&
                "bg-muted font-semibold",
            )}
            onClick={() => setActiveTab(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {activeTab === "api-key" ? (
        <ApiKeyList />
      ) : (
        <ProviderList type={activeTab} />
      )}
    </div>
  );
}
