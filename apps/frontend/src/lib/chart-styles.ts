/**
 * Recharts 圖表樣式共用設定 — Token-Gov.6
 *
 * 之前 5 個 chart 元件各自重複 tooltip style；提取到此處作為 single source of truth，
 * 同時明確指定文字色，確保在 light / dark theme 下文字都清晰可讀。
 *
 * 使用：
 *   import { CHART_TOOLTIP } from "@/lib/chart-styles";
 *   <Tooltip {...CHART_TOOLTIP} formatter={...} />
 */

/**
 * Tooltip 全套樣式（contentStyle / itemStyle / labelStyle / cursor）。
 * 可解構展開到 `<Tooltip>` 上：`<Tooltip {...CHART_TOOLTIP} />`
 */
export const CHART_TOOLTIP = {
  contentStyle: {
    background: "oklch(0.14 0.02 250)",
    border: "1px solid oklch(0.75 0.15 195 / 30%)",
    borderRadius: "8px",
    padding: "8px 12px",
    fontSize: "13px",
    // 明確指定主要文字色 — 避免在 light theme 下預設黑字看不清
    color: "oklch(0.98 0 0)",
    boxShadow: "0 4px 12px oklch(0 0 0 / 25%)",
  },
  /** 每個數據項的文字色（value + name） */
  itemStyle: {
    color: "oklch(0.98 0 0)",
  },
  /** 標題列（例如 x 軸值 / 日期）的文字色 */
  labelStyle: {
    color: "oklch(0.75 0.15 195)",
    marginBottom: "4px",
    fontWeight: 500,
  },
  /** hover 時 bar / area 的高亮色（淡 accent）*/
  cursor: { fill: "oklch(0.75 0.15 195 / 8%)" },
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
