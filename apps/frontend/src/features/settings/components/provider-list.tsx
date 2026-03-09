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

export function ProviderList() {
  const { data: settings, isLoading } = useProviderSettings("llm");
  const { data: registry } = useModelRegistry();
  const createMutation = useCreateProviderSetting();
  const updateMutation = useUpdateProviderSetting();

  const findSetting = (providerName: string): ProviderSetting | undefined =>
    settings?.find(
      (s) =>
        s.provider_name === providerName && s.provider_type === "llm",
    );

  function handleToggle(
    providerName: string,
    currentSetting: ProviderSetting | undefined,
  ) {
    if (!currentSetting) {
      createMutation.mutate({
        provider_type: "llm",
        provider_name: providerName,
        display_name: PROVIDER_LABELS[providerName] ?? providerName,
      });
    } else {
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
          createMutation.isPending &&
          (createMutation.variables as { provider_name?: string })
            ?.provider_name === providerName;

        const switchId = `toggle-${providerName}-llm`;

        return (
          <Card
            key={providerName}
            className={`transition-all duration-200 hover:shadow-md ${
              !isEnabled ? "opacity-50" : ""
            }`}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {PROVIDER_LABELS[providerName] ?? providerName}
                </CardTitle>
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
              </div>
              <Badge variant="outline" className="w-fit">
                LLM
              </Badge>
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
                registry?.[providerName]?.llm?.length ? (
                <>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    啟用後可用模型
                  </p>
                  <div className="space-y-1">
                    {registry[providerName].llm.map((m) => (
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
                    className={`text-[10px] ${setting.has_api_key ? "border-green-500 text-green-600 dark:border-green-400 dark:text-green-400" : ""}`}
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
