import { useState } from "react";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useProviderSettings,
  useCreateProviderSetting,
  useUpdateProviderSetting,
  useModelRegistry,
} from "@/hooks/queries/use-provider-settings";
import type { ProviderSetting } from "@/types/provider-setting";
import { PROVIDER_LABELS, PROVIDER_ORDER } from "@/types/provider-setting";

interface ProviderListProps {
  type: string;
}

export function ProviderList({ type }: ProviderListProps) {
  const { data: settings, isLoading } = useProviderSettings(type);
  const { data: registry } = useModelRegistry();
  const createMutation = useCreateProviderSetting();
  const updateMutation = useUpdateProviderSetting();

  // Track which provider is showing the "cannot disable" warning
  const [disableWarning, setDisableWarning] = useState<string | null>(null);

  const findSetting = (providerName: string): ProviderSetting | undefined =>
    settings?.find(
      (s) =>
        s.provider_name === providerName && s.provider_type === type,
    );

  function handleToggle(
    providerName: string,
    currentSetting: ProviderSetting | undefined,
  ) {
    if (!currentSetting) {
      createMutation.mutate({
        provider_type: type,
        provider_name: providerName,
        display_name: PROVIDER_LABELS[providerName] ?? providerName,
      });
    } else if (
      currentSetting.is_enabled &&
      type === "embedding" &&
      currentSetting.models.some((m) => m.is_default)
    ) {
      // Prevent disabling embedding provider when a model is selected
      setDisableWarning(providerName);
      setTimeout(() => setDisableWarning(null), 3000);
    } else {
      setDisableWarning(null);
      updateMutation.mutate({
        id: currentSetting.id,
        data: { is_enabled: !currentSetting.is_enabled },
      });
    }
  }

  function handleModelToggle(setting: ProviderSetting, modelId: string) {
    const updatedModels = setting.models.map((m) =>
      m.model_id === modelId ? { ...m, is_enabled: !m.is_enabled } : m,
    );
    updateMutation.mutate({
      id: setting.id,
      data: { models: updatedModels },
    });
  }

  function handleDefaultModelChange(
    setting: ProviderSetting,
    modelId: string,
  ) {
    const updatedModels = setting.models.map((m) => ({
      ...m,
      is_default: m.model_id === modelId,
      is_enabled: m.model_id === modelId ? true : m.is_enabled,
    }));
    updateMutation.mutate({
      id: setting.id,
      data: { models: updatedModels },
    });
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-56 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {PROVIDER_ORDER.map((providerName) => {
        const setting = findSetting(providerName);
        const isEnabled = setting?.is_enabled ?? false;
        const isBusy =
          (updateMutation.isPending &&
            updateMutation.variables?.id === setting?.id) ||
          (createMutation.isPending &&
            (createMutation.variables as { provider_name?: string })
              ?.provider_name === providerName);

        const switchId = `toggle-${providerName}-${type}`;

        return (
          <Card
            key={`${providerName}-${type}`}
            className={`transition-all duration-200 hover:shadow-md ${
              !isEnabled ? "opacity-50" : ""
            }`}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {PROVIDER_LABELS[providerName] ?? providerName}
                </CardTitle>
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-2">
                    <Label
                      htmlFor={switchId}
                      className="text-xs text-muted-foreground"
                    >
                      {isEnabled ? "啟用" : "停用"}
                    </Label>
                    <Switch
                      id={switchId}
                      checked={isEnabled}
                      onCheckedChange={() =>
                        handleToggle(providerName, setting)
                      }
                      disabled={isBusy}
                      aria-label={`${isEnabled ? "停用" : "啟用"} ${PROVIDER_LABELS[providerName] ?? providerName}`}
                    />
                  </div>
                  {disableWarning === providerName && (
                    <p className="text-[11px] font-medium text-destructive">
                      有模型使用中，無法停用
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="w-fit">
                  {type.toUpperCase()}
                </Badge>
                {type === "embedding" &&
                  isEnabled &&
                  setting?.models.some((m) => m.is_default) && (
                    <Badge variant="default" className="w-fit">
                      目前使用中
                    </Badge>
                  )}
              </div>
            </CardHeader>
            <CardContent>
              {setting && setting.models.length > 0 ? (
                <>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    可用模型
                  </p>
                  <div className="space-y-1">
                    {setting.models.map((m) => (
                      <div
                        key={m.model_id}
                        className="flex items-center justify-between rounded-md border bg-muted/30 px-2.5 py-1.5 text-xs"
                      >
                        <div className="flex items-center gap-2">
                          {type === "embedding" ? (
                            <input
                              type="radio"
                              name="embedding-active-model"
                              checked={m.is_default}
                              onChange={() =>
                                handleDefaultModelChange(
                                  setting,
                                  m.model_id,
                                )
                              }
                              disabled={!isEnabled || isBusy}
                              className="border-input"
                              aria-label={`選用模型 ${m.display_name}`}
                            />
                          ) : (
                            <input
                              type="checkbox"
                              checked={m.is_enabled}
                              onChange={() =>
                                handleModelToggle(setting, m.model_id)
                              }
                              disabled={!isEnabled || isBusy}
                              className="rounded border-input"
                              aria-label={`啟用模型 ${m.display_name}`}
                            />
                          )}
                          <div>
                            <span className="font-medium">
                              {m.display_name}
                            </span>
                            <span className="ml-1.5 font-mono text-muted-foreground">
                              {m.model_id}
                            </span>
                          </div>
                        </div>
                        <span className="shrink-0 text-muted-foreground">
                          {m.price}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : !setting &&
                registry?.[providerName]?.[type]?.length ? (
                <>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    啟用後可用模型
                  </p>
                  <div className="space-y-1">
                    {registry[providerName][type].map((m) => (
                      <div
                        key={m.model_id}
                        className="flex items-center justify-between rounded-md border bg-muted/10 px-2.5 py-1.5 text-xs opacity-60"
                      >
                        <div>
                          <span className="font-medium">
                            {m.display_name}
                          </span>
                          <span className="ml-1.5 font-mono text-muted-foreground">
                            {m.model_id}
                          </span>
                        </div>
                        <span className="shrink-0 text-muted-foreground">
                          {m.price}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-xs text-muted-foreground">
                  {setting ? "無可用模型" : "未啟用"}
                </p>
              )}
              {setting && (
                <div className="mt-3 flex items-center gap-1.5">
                  <span className="text-[11px] text-muted-foreground">
                    API Key
                  </span>
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${setting.has_api_key ? "border-green-500 text-green-600" : ""}`}
                  >
                    {setting.has_api_key ? "已設定" : "未設定"}
                  </Badge>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
