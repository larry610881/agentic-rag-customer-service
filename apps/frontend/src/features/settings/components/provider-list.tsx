import { useState } from "react";
import { Plug, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  useProviderSettings,
  useDeleteProviderSetting,
  useUpdateProviderSetting,
} from "@/hooks/queries/use-provider-settings";
import type { ProviderSetting } from "@/types/provider-setting";
import { PROVIDER_MODELS } from "@/lib/provider-models";
import { ProviderFormDialog } from "./provider-form-dialog";

interface ProviderListProps {
  type?: string;
}

export function ProviderList({ type }: ProviderListProps) {
  const { data: providers, isLoading } = useProviderSettings(type);
  const deleteMutation = useDeleteProviderSetting();
  const updateMutation = useUpdateProviderSetting();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSetting, setEditingSetting] =
    useState<ProviderSetting | null>(null);

  const handleToggleEnabled = (provider: ProviderSetting) => {
    updateMutation.mutate({
      id: provider.id,
      data: { is_enabled: !provider.is_enabled },
    });
  };

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-48 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          {type === "llm" ? "LLM" : type === "embedding" ? "Embedding" : "全部"}
          供應商
        </h2>
        <Button
          size="sm"
          onClick={() => {
            setEditingSetting(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="mr-1 h-4 w-4" />
          新增供應商
        </Button>
      </div>

      {(!providers || providers.length === 0) && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-muted-foreground">
          <Plug className="mb-2 h-8 w-8" />
          <p>尚未設定供應商</p>
          <Button
            variant="link"
            size="sm"
            onClick={() => {
              setEditingSetting(null);
              setDialogOpen(true);
            }}
          >
            立即新增
          </Button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {providers?.map((provider) => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            onToggleEnabled={() => handleToggleEnabled(provider)}
            isToggling={
              updateMutation.isPending &&
              updateMutation.variables?.id === provider.id
            }
            onEdit={() => {
              setEditingSetting(provider);
              setDialogOpen(true);
            }}
            onDelete={() => deleteMutation.mutate(provider.id)}
          />
        ))}
      </div>

      <ProviderFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editingSetting={editingSetting}
        defaultType={type}
      />
    </div>
  );
}

interface ProviderCardProps {
  provider: ProviderSetting;
  onToggleEnabled: () => void;
  isToggling: boolean;
  onEdit: () => void;
  onDelete: () => void;
}

function ProviderCard({
  provider,
  onToggleEnabled,
  isToggling,
  onEdit,
  onDelete,
}: ProviderCardProps) {
  const providerType = provider.provider_type as "llm" | "embedding";
  const modelGroup = PROVIDER_MODELS[provider.provider_name];
  const models = modelGroup?.[providerType] ?? [];

  return (
    <Card
      className={`transition-all duration-200 hover:shadow-md ${
        !provider.is_enabled ? "opacity-60" : ""
      }`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{provider.display_name}</CardTitle>
          <div className="flex items-center gap-2">
            <Label
              htmlFor={`toggle-${provider.id}`}
              className="text-xs text-muted-foreground"
            >
              {provider.is_enabled ? "啟用" : "停用"}
            </Label>
            <Switch
              id={`toggle-${provider.id}`}
              checked={provider.is_enabled}
              onCheckedChange={onToggleEnabled}
              disabled={isToggling}
              aria-label={`${provider.is_enabled ? "停用" : "啟用"} ${provider.display_name}`}
            />
          </div>
        </div>
        <div className="flex gap-1">
          <Badge variant="outline">{provider.provider_type}</Badge>
          <Badge variant="outline">{provider.provider_name}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* 模型清單 + 價格 */}
        {models.length > 0 ? (
          <div className="mb-3 space-y-1">
            <p className="text-xs font-medium text-muted-foreground">
              可用模型
            </p>
            <div className="flex flex-wrap gap-1.5">
              {models.map((m) => (
                <span
                  key={m.id}
                  className="inline-flex items-center gap-1 rounded-md border bg-muted/40 px-2 py-0.5 text-xs"
                >
                  {m.name}
                  <span className="text-muted-foreground">{m.price}</span>
                </span>
              ))}
            </div>
          </div>
        ) : (
          <p className="mb-3 text-xs text-muted-foreground">
            無預設模型清單
          </p>
        )}

        <p className="mb-3 text-xs text-muted-foreground">
          API Key 由 .env 管理
        </p>

        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>
            編輯
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDelete}
            className="ml-auto text-destructive hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
