import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useProviderSettings,
  useCreateProviderSetting,
  useUpdateProviderSetting,
} from "@/hooks/queries/use-provider-settings";
import type { ProviderSetting } from "@/types/provider-setting";
import {
  PROVIDER_MODELS,
  PROVIDER_LABELS,
  PROVIDER_ORDER,
} from "@/lib/provider-models";

interface ProviderListProps {
  type?: string;
}

/** Pre-defined card: one per (provider, type) that has models */
interface PreDefinedCard {
  providerName: string;
  providerType: "llm" | "embedding";
  label: string;
  models: { id: string; name: string; price: string }[];
}

function buildPreDefinedCards(typeFilter?: string): PreDefinedCard[] {
  const cards: PreDefinedCard[] = [];
  for (const name of PROVIDER_ORDER) {
    const group = PROVIDER_MODELS[name];
    if (!group) continue;
    const label = PROVIDER_LABELS[name] ?? name;

    if ((!typeFilter || typeFilter === "llm") && group.llm.length > 0) {
      cards.push({
        providerName: name,
        providerType: "llm",
        label: `${label}`,
        models: group.llm,
      });
    }
    if (
      (!typeFilter || typeFilter === "embedding") &&
      group.embedding.length > 0
    ) {
      cards.push({
        providerName: name,
        providerType: "embedding",
        label: `${label}`,
        models: group.embedding,
      });
    }
  }
  return cards;
}

export function ProviderList({ type }: ProviderListProps) {
  const { data: dbSettings, isLoading } = useProviderSettings();
  const createMutation = useCreateProviderSetting();
  const updateMutation = useUpdateProviderSetting();

  const cards = buildPreDefinedCards(type);

  /** Find matching DB record for a pre-defined card */
  const findSetting = (
    providerName: string,
    providerType: string,
  ): ProviderSetting | undefined =>
    dbSettings?.find(
      (s) =>
        s.provider_name === providerName &&
        s.provider_type === providerType,
    );

  const handleToggle = (card: PreDefinedCard, current: boolean) => {
    const existing = findSetting(card.providerName, card.providerType);

    if (existing) {
      // Toggle existing record
      updateMutation.mutate({
        id: existing.id,
        data: { is_enabled: !current },
      });
    } else {
      // First time enable → create record
      createMutation.mutate({
        provider_type: card.providerType,
        provider_name: card.providerName,
        display_name: `${card.label} (${card.providerType.toUpperCase()})`,
        api_key: "",
      });
    }
  };

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
      {cards.map((card) => {
        const setting = findSetting(card.providerName, card.providerType);
        const isEnabled = setting?.is_enabled ?? false;
        const isBusy =
          (updateMutation.isPending &&
            updateMutation.variables?.id === setting?.id) ||
          (createMutation.isPending &&
            (createMutation.variables as { provider_name?: string })
              ?.provider_name === card.providerName);

        return (
          <ProviderCard
            key={`${card.providerName}-${card.providerType}`}
            card={card}
            isEnabled={isEnabled}
            isBusy={isBusy}
            onToggle={() => handleToggle(card, isEnabled)}
          />
        );
      })}
    </div>
  );
}

interface ProviderCardProps {
  card: PreDefinedCard;
  isEnabled: boolean;
  isBusy: boolean;
  onToggle: () => void;
}

function ProviderCard({
  card,
  isEnabled,
  isBusy,
  onToggle,
}: ProviderCardProps) {
  const switchId = `toggle-${card.providerName}-${card.providerType}`;

  return (
    <Card
      className={`transition-all duration-200 hover:shadow-md ${
        !isEnabled ? "opacity-50" : ""
      }`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{card.label}</CardTitle>
          <div className="flex items-center gap-2">
            <Label htmlFor={switchId} className="text-xs text-muted-foreground">
              {isEnabled ? "啟用" : "停用"}
            </Label>
            <Switch
              id={switchId}
              checked={isEnabled}
              onCheckedChange={onToggle}
              disabled={isBusy}
              aria-label={`${isEnabled ? "停用" : "啟用"} ${card.label}`}
            />
          </div>
        </div>
        <Badge variant="outline" className="w-fit">
          {card.providerType.toUpperCase()}
        </Badge>
      </CardHeader>
      <CardContent>
        <p className="mb-2 text-xs font-medium text-muted-foreground">
          可用模型
        </p>
        <div className="space-y-1">
          {card.models.map((m) => (
            <div
              key={m.id}
              className="flex items-center justify-between rounded-md border bg-muted/30 px-2.5 py-1.5 text-xs"
            >
              <div>
                <span className="font-medium">{m.name}</span>
                <span className="ml-1.5 font-mono text-muted-foreground">
                  {m.id}
                </span>
              </div>
              <span className="shrink-0 text-muted-foreground">{m.price}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-muted-foreground">
          API Key 由伺服器 .env 管理
        </p>
      </CardContent>
    </Card>
  );
}
