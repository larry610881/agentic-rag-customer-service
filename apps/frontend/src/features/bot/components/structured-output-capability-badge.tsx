import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useStructuredOutputCapability } from "@/hooks/queries/use-structured-output-capability";
import {
  CAPABILITY_ERROR_LABEL,
  CAPABILITY_LOADING_LABEL,
  CAPABILITY_NO_MODEL_LABEL,
  STRUCTURED_OUTPUT_TIER_LABELS,
  type CapabilityTone,
} from "@/features/bot/output-format-labels";

type StructuredOutputCapabilityBadgeProps = {
  provider?: string;
  model?: string;
};

const TONE_CLASS: Record<CapabilityTone, string> = {
  success:
    "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  warning:
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200",
  danger:
    "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200",
  neutral: "",
};

/**
 * Issue #70 — 依 bot 目前選的供應商 / 模型顯示 JSON 結構化輸出能力等級
 * （A 原生 schema / B 僅 JSON / C 純 prompt）。provider / model 未選時提示先選模型。
 */
export function StructuredOutputCapabilityBadge({
  provider,
  model,
}: StructuredOutputCapabilityBadgeProps) {
  const ready = !!provider && !!model;
  const { data, isLoading, isError } = useStructuredOutputCapability(
    provider,
    model,
  );

  let label = CAPABILITY_NO_MODEL_LABEL;
  let tone: CapabilityTone = "neutral";
  let note = "";
  if (ready) {
    if (data) {
      const meta = STRUCTURED_OUTPUT_TIER_LABELS[data.tier];
      label = meta.label;
      tone = meta.tone;
      note = data.note;
    } else if (isLoading) {
      label = CAPABILITY_LOADING_LABEL;
    } else if (isError) {
      label = CAPABILITY_ERROR_LABEL;
    }
  }

  return (
    <div
      className="flex flex-wrap items-center gap-2"
      data-tier={data?.tier ?? ""}
    >
      <Badge
        variant="outline"
        role="status"
        aria-label="結構化輸出能力"
        className={cn("whitespace-normal", TONE_CLASS[tone])}
      >
        {label}
      </Badge>
      {note && <span className="text-xs text-muted-foreground">{note}</span>}
    </div>
  );
}
