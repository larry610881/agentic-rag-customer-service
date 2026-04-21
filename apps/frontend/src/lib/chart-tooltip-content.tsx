import type { ReactElement } from "react";

type FormatterResult = [string, string] | string;

export type ChartTooltipFormatter = (
  value: number,
  name: string,
) => FormatterResult;

type PayloadEntry = {
  value?: number | string;
  name?: string | number;
  color?: string;
};

export type ChartTooltipContentProps = {
  active?: boolean;
  payload?: ReadonlyArray<PayloadEntry>;
  label?: string | number;
  formatter?: ChartTooltipFormatter;
  showIndicator?: boolean;
  labelOverride?: string;
};

/**
 * 圖表 Tooltip 內容 — Token-Gov.6 (UX)。
 *
 * 取代原先 CHART_TOOLTIP 的 inline-style 方案：recharts 內建 tooltip 的
 * per-item 文字色會被 payload.color (series 顏色) 覆蓋 itemStyle.color，
 * 在深色 popover 上會造成「看得到 tooltip 方塊但看不到文字」的體感。
 *
 * 改走 Tailwind `bg-popover` / `text-popover-foreground`：自動跟隨 theme，
 * 文字色穩定、有明確的 indicator dot 傳達 series color，不再依賴 recharts 內部行為。
 */
export function ChartTooltipContent({
  active,
  payload,
  label,
  formatter,
  showIndicator = true,
  labelOverride,
}: ChartTooltipContentProps): ReactElement | null {
  if (!active || !payload?.length) return null;
  const displayLabel =
    labelOverride ?? (label !== undefined && label !== "" ? String(label) : "");

  return (
    <div className="min-w-[140px] rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      {displayLabel && (
        <p className="mb-1 font-medium text-muted-foreground">{displayLabel}</p>
      )}
      <ul className="space-y-1">
        {payload.map((entry, idx) => {
          const rawValue = Number(entry.value ?? 0);
          const rawName = String(entry.name ?? "");
          let displayValue: string;
          let displayName: string;
          if (formatter) {
            const res = formatter(rawValue, rawName);
            if (Array.isArray(res)) {
              [displayValue, displayName] = res;
            } else {
              displayValue = res;
              displayName = rawName;
            }
          } else {
            displayValue = rawValue.toLocaleString();
            displayName = rawName;
          }
          return (
            <li key={idx} className="flex items-center gap-2">
              {showIndicator && entry.color && (
                <span
                  aria-hidden
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                  style={{ background: String(entry.color) }}
                />
              )}
              <span className="text-muted-foreground">{displayName}</span>
              <span className="ml-auto font-mono tabular-nums text-foreground">
                {displayValue}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
