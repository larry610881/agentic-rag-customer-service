/**
 * Recharts 圖表樣式共用設定 — Token-Gov.6 (+ UX 補丁)。
 *
 * 原 `CHART_TOOLTIP` (inline-style 展開到 <Tooltip>) 已棄用：recharts 內建 tooltip
 * 的 per-item 色彩會覆蓋 itemStyle.color，在深色背景下文字會被染成 series 顏色，
 * 造成「看得到方塊但看不到內容」。
 *
 * 新做法：改用 `<Tooltip content={<ChartTooltipContent formatter={...} />} />`
 * 走 Tailwind `bg-popover` / `text-popover-foreground`，自動跟隨 light/dark theme。
 *
 * cursor（bar/line hover 時的強調條）仍維持 inline style，因為它不涉及文字。
 */

/** Bar / Line hover 時的強調條顏色（淡 accent） */
export const CHART_TOOLTIP_CURSOR = {
  fill: "oklch(0.75 0.15 195 / 8%)",
} as const;

/**
 * Chart 系列主色（線條 / bar / pie cell 用）。
 * OKLCH 色彩空間 — 在 light / dark theme 都能保持一致對比。
 */
export const CHART_COLORS = [
  "oklch(0.65 0.20 250)", // 藍
  "oklch(0.70 0.18 150)", // 綠
  "oklch(0.65 0.20 25)",  // 紅橘
  "oklch(0.70 0.16 80)",  // 金黃
  "oklch(0.60 0.15 300)", // 紫
  "oklch(0.55 0.12 330)", // 粉
  "oklch(0.65 0.18 50)",  // 橘
] as const;

/** Pie / slice label 的文字色（切片中間的 `xxx 51%`），確保在深 cell 上清楚 */
export const CHART_LABEL_FILL = "oklch(0.98 0 0)";
