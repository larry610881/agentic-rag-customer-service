import { useState } from "react";
import { Plug, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useProviderSettings,
  useDeleteProviderSetting,
} from "@/hooks/queries/use-provider-settings";
import type { ProviderSetting } from "@/types/provider-setting";
import { ProviderFormDialog } from "./provider-form-dialog";

interface ProviderListProps {
  type?: string;
}

export function ProviderList({ type }: ProviderListProps) {
  const { data: providers, isLoading } = useProviderSettings(type);
  const deleteMutation = useDeleteProviderSetting();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSetting, setEditingSetting] =
    useState<ProviderSetting | null>(null);

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
  onEdit: () => void;
  onDelete: () => void;
}

function ProviderCard({
  provider,
  onEdit,
  onDelete,
}: ProviderCardProps) {
  return (
    <Card
      className="transition-shadow duration-200 hover:shadow-md"
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{provider.display_name}</CardTitle>
          <Badge variant={provider.is_enabled ? "default" : "secondary"}>
            {provider.is_enabled ? "啟用" : "停用"}
          </Badge>
        </div>
        <div className="flex gap-1">
          <Badge variant="outline">{provider.provider_type}</Badge>
          <Badge variant="outline">{provider.provider_name}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-3 space-y-1 text-sm text-muted-foreground">
          {provider.models.length > 0 && (
            <p>
              模型:{" "}
              {provider.models.map((m) => m.display_name).join(", ")}
            </p>
          )}
          <p className="text-xs">API Key 由 .env 管理</p>
        </div>
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
