import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { guardStageDefsFor } from "@/features/guard-stages/guard-stage-labels";

export interface GuardStageChecklistProps {
  /** 控制項 id 前綴；同頁多份清單時需區分 */
  idPrefix: string;
  /** 目前勾選的階段 */
  selected: string[];
  onToggle: (stage: string, checked: boolean) => void;
  /** 個別階段是否不可改（底線 / 上層已啟用 / 預留） */
  isDisabled?: (stage: string) => boolean;
  /** 整份清單唯讀（鎖定 / 載入中） */
  disabledAll?: boolean;
  /** 每個階段右側的來源徽章文字；undefined = 不顯示 */
  badgeOf?: (stage: string) => string | undefined;
  /** 清單標題列右側的額外內容（例如提示） */
  header?: ReactNode;
  /** 全集（後端 available_stages / stages）；缺時用前端宣告的五個階段 */
  stages?: string[];
}

/**
 * 防護階段勾選清單（bot 表單、租戶設定、方案共用）。
 * 使用原生 checkbox 與 bot 表單既有樣式一致，jsdom 可直接測。
 */
export function GuardStageChecklist({
  idPrefix,
  selected,
  onToggle,
  isDisabled,
  disabledAll = false,
  badgeOf,
  header,
  stages,
}: GuardStageChecklistProps) {
  const defs = guardStageDefsFor(stages);
  return (
    <div className="space-y-2">
      {header}
      <ul className="divide-y rounded-md border">
        {defs.map((def) => {
          const id = `${idPrefix}-${def.key}`;
          const checked = selected.includes(def.key);
          const disabled = disabledAll || def.comingSoon === true || (isDisabled?.(def.key) ?? false);
          const badge = badgeOf?.(def.key);
          return (
            <li key={def.key} className="flex items-start gap-3 px-3 py-2.5">
              <input
                id={id}
                type="checkbox"
                className="mt-1 rounded border-input"
                checked={checked}
                disabled={disabled}
                aria-label={def.label}
                onChange={(e) => onToggle(def.key, e.target.checked)}
              />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  <label htmlFor={id} className="text-sm font-medium">
                    {def.label}
                  </label>
                  {def.comingSoon && <Badge variant="outline">即將推出</Badge>}
                  {badge && (
                    <Badge variant="secondary" className="font-normal">
                      {badge}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">{def.description}</p>
                {def.costHint && (
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    成本：{def.costHint}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
