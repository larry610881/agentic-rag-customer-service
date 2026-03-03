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

/** Group settings by provider_name — same vendor shares one key. */
function groupByProvider(settings: ProviderSetting[]) {
  const map = new Map<string, ProviderSetting[]>();
  for (const s of settings) {
    const group = map.get(s.provider_name) ?? [];
    group.push(s);
    map.set(s.provider_name, group);
  }
  return map;
}

export function ApiKeyList() {
  const { data: settings, isLoading } = useProviderSettings();
  const updateMutation = useUpdateProviderSetting();

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<string | null>(null);
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSave(providerName: string, group: ProviderSetting[]) {
    const key = drafts[providerName]?.trim();
    if (!key) return;

    setSavingProvider(providerName);
    setError(null);

    try {
      // Use mutateAsync + Promise.all to properly await all mutations
      await Promise.all(
        group.map((setting) =>
          updateMutation.mutateAsync({
            id: setting.id,
            data: { api_key: key },
          }),
        ),
      );
      setDrafts((prev) => ({ ...prev, [providerName]: "" }));
      setSaved(providerName);
      setTimeout(() => setSaved(null), 2500);
    } catch {
      setError(providerName);
      setTimeout(() => setError(null), 3000);
    } finally {
      setSavingProvider(null);
    }
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

  const providers = settings?.filter(Boolean) ?? [];
  const grouped = groupByProvider(providers);

  if (grouped.size === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        尚未啟用任何供應商。請先在 LLM 頁籤啟用供應商。
      </p>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {[...grouped.entries()].map(([providerName, group]) => {
        const hasKey = group.some((s) => s.has_api_key);
        const types = group.map((s) => s.provider_type.toUpperCase());
        const isBusy = savingProvider === providerName;
        const isSaved = saved === providerName;
        const isError = error === providerName;

        return (
          <Card
            key={providerName}
            className="transition-all duration-200 hover:shadow-md"
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {PROVIDER_LABELS[providerName] ?? providerName}
                </CardTitle>
                {isSaved ? (
                  <Badge
                    variant="outline"
                    className="border-green-500 text-green-600"
                  >
                    ✓ 已更新
                  </Badge>
                ) : isError ? (
                  <Badge
                    variant="outline"
                    className="border-destructive text-destructive"
                  >
                    更新失敗
                  </Badge>
                ) : (
                  <Badge
                    variant="outline"
                    className={
                      hasKey ? "border-green-500 text-green-600" : ""
                    }
                  >
                    {hasKey ? "已設定" : "未設定"}
                  </Badge>
                )}
              </div>
              <div className="flex gap-1.5">
                {types.map((t) => (
                  <Badge
                    key={t}
                    variant="outline"
                    className="w-fit text-[10px]"
                  >
                    {t}
                  </Badge>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder="輸入新的 API Key"
                  value={drafts[providerName] ?? ""}
                  onChange={(e) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [providerName]: e.target.value,
                    }))
                  }
                  disabled={isBusy}
                  className="h-8 text-sm"
                />
                <Button
                  type="button"
                  size="sm"
                  className="h-8 shrink-0"
                  disabled={!drafts[providerName]?.trim() || isBusy}
                  onClick={() => handleSave(providerName, group)}
                >
                  {isBusy ? (
                    <span className="flex items-center gap-1.5">
                      <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      儲存中
                    </span>
                  ) : (
                    "更新"
                  )}
                </Button>
              </div>
              <p className="mt-2 text-[11px] text-muted-foreground">
                同一供應商的 LLM 與 Embedding 共用此 Key，以 AES-256
                加密儲存。
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
