import type { CreateBotRequest } from "@/types/bot";
import { KB_MODE_RECOMMENDED_SCORE_THRESHOLD } from "./output-format-labels";

/** 建立機器人的快速範本 */
export type CreateBotPreset = "default" | "kb_qa";

/**
 * Issue #70 — 「知識庫問答」預設組：檢索 → 單次生成，無工具、無記憶、無 rerank，
 * 純文字輸出並顯示來源；相關度門檻拉到 0.5（平台預設 0.3 對 kb 模式偏鬆）。
 */
export const KB_QA_BOT_PRESET: Readonly<
  Pick<
    CreateBotRequest,
    | "mode"
    | "enabled_tools"
    | "memory_enabled"
    | "rerank_enabled"
    | "output_format"
    | "show_sources"
    | "rag_score_threshold"
  >
> = Object.freeze({
  mode: "kb",
  enabled_tools: ["rag_query"],
  memory_enabled: false,
  rerank_enabled: false,
  output_format: "plain_text",
  show_sources: true,
  rag_score_threshold: KB_MODE_RECOMMENDED_SCORE_THRESHOLD,
});

export const CREATE_BOT_PRESET_LABELS: Record<
  CreateBotPreset,
  { label: string; hint: string }
> = {
  default: { label: "一般客服", hint: "深度推理、全部工具，建立後再細調" },
  kb_qa: {
    label: "知識庫問答",
    hint: "只做檢索與一次生成，無工具 / 記憶 / rerank；純文字輸出、顯示來源、門檻 0.5",
  },
};
