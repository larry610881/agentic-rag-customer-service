import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useProviderSettings,
  useUpdateProviderSetting,
} from "@/hooks/queries/use-provider-settings";
import type { ProviderSetting } from "@/types/provider-setting";
import { PROVIDER_LABELS } from "@/types/provider-setting";

export function ApiKeyList() {
  const { data: settings, isLoading } = useProviderSettings();
  const updateMutation = useUpdateProviderSetting();

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<string | null>(null);

  function handleSave(setting: ProviderSetting) {
    const key = drafts[setting.id]?.trim();
    if (!key) return;
    updateMutation.mutate(
      { id: setting.id, data: { api_key: key } },
      {
        onSuccess: () => {
          setDrafts((prev) => ({ ...prev, [setting.id]: "" }));
          setSaved(setting.id);
          setTimeout(() => setSaved(null), 2000);
        },
      },
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-36 rounded-lg" />
        ))}
      </div>
    );
  }

  // Only show providers that have been created (enabled at least once)
  const providers = settings?.filter(Boolean) ?? [];

  if (providers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        尚未啟用任何供應商。請先在 LLM 或 Embedding 頁籤啟用供應商。
      </p>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {providers.map((setting) => {
        const isBusy =
          updateMutation.isPending &&
          updateMutation.variables?.id === setting.id;

        return (
          <Card
            key={setting.id}
            className="transition-all duration-200 hover:shadow-md"
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {PROVIDER_LABELS[setting.provider_name] ??
                    setting.display_name}
                </CardTitle>
                {saved === setting.id ? (
                  <Badge
                    variant="outline"
                    className="border-green-500 text-green-600"
                  >
                    已更新
                  </Badge>
                ) : (
                  <Badge
                    variant="outline"
                    className={
                      setting.has_api_key
                        ? "border-green-500 text-green-600"
                        : ""
                    }
                  >
                    {setting.has_api_key ? "已設定" : "未設定"}
                  </Badge>
                )}
              </div>
              <Badge variant="outline" className="w-fit text-[10px]">
                {setting.provider_type.toUpperCase()}
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder="輸入新的 API Key"
                  value={drafts[setting.id] ?? ""}
                  onChange={(e) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [setting.id]: e.target.value,
                    }))
                  }
                  className="h-8 text-sm"
                />
                <Button
                  type="button"
                  size="sm"
                  className="h-8 shrink-0"
                  disabled={!drafts[setting.id]?.trim() || isBusy}
                  onClick={() => handleSave(setting)}
                >
                  {isBusy ? "更新中..." : "更新"}
                </Button>
              </div>
              <p className="mt-2 text-[11px] text-muted-foreground">
                Key 以 AES-256 加密儲存，不會明文顯示。
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
