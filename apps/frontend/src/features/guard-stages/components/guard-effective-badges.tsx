import { Badge } from "@/components/ui/badge";
import {
  guardSourceLabel,
  guardStageLabel,
  sortGuardStages,
} from "@/features/guard-stages/guard-stage-labels";
import type { GuardEffective } from "@/types/guard-stages";

interface GuardEffectiveBadgesProps {
  effective: GuardEffective;
}

/** 有效階段徽章：「階段名 · 來源」，底線用實心、其餘外框 */
export function GuardEffectiveBadges({ effective }: GuardEffectiveBadgesProps) {
  const stages = sortGuardStages(effective.stages);
  if (stages.length === 0) {
    return <span className="text-muted-foreground">（未啟用任何階段）</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {stages.map((stage) => {
        const source = effective.source_map[stage];
        const isRequired = source === "required" || effective.required.includes(stage);
        return (
          <Badge
            key={stage}
            variant={isRequired ? "default" : "outline"}
            className="font-normal"
            data-testid={`effective-stage-${stage}`}
          >
            {guardStageLabel(stage)} · {isRequired ? "底線" : guardSourceLabel(source)}
          </Badge>
        );
      })}
    </div>
  );
}
