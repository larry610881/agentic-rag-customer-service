"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ProviderList } from "@/features/settings/components/provider-list";

const tabs = [
  { value: undefined, label: "全部" },
  { value: "llm", label: "LLM" },
  { value: "embedding", label: "Embedding" },
] as const;

export default function ProvidersSettingsPage() {
  const [activeTab, setActiveTab] = useState<string | undefined>(undefined);

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">供應商設定</h1>
        <p className="text-muted-foreground">
          管理 LLM 與 Embedding 供應商的 API 金鑰與模型設定
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

      <ProviderList type={activeTab} />
    </div>
  );
}
