/**
 * Usage Category single source of truth — Token-Gov.6
 *
 * 對應後端 `src/domain/usage/category.py` 的 `UsageCategory` enum (12 個具名值)。
 * 凡是要把 request_type 字串顯示成中文的地方（dialog / table / chart / admin page）
 * 都應 import 本檔的 `getCategoryLabel` / `getCategoryShortLabel`，不要各自寫 map。
 *
 * label     — 完整中文（dialog / 說明 / 長欄位）
 * shortLabel — 短中文（table / chart / 窄欄）
 */

export type UsageCategoryDef = {
  value: string;
  label: string;
  shortLabel: string;
};

export const USAGE_CATEGORIES: readonly UsageCategoryDef[] = [
  { value: "rag", label: "RAG 查詢", shortLabel: "RAG" },
  { value: "chat_web", label: "Web 對話", shortLabel: "Web" },
  { value: "chat_widget", label: "Widget 對話", shortLabel: "Widget" },
  { value: "chat_line", label: "LINE 對話", shortLabel: "LINE" },
  { value: "ocr", label: "OCR", shortLabel: "OCR" },
  { value: "embedding", label: "Embedding", shortLabel: "Embedding" },
  { value: "guard", label: "Prompt Guard", shortLabel: "Guard" },
  { value: "rerank", label: "LLM Reranker", shortLabel: "Rerank" },
  { value: "contextual_retrieval", label: "Contextual Retrieval", shortLabel: "Contextual" },
  { value: "pdf_rename", label: "PDF 子頁 Rename", shortLabel: "PDF Rename" },
  { value: "auto_classification", label: "Auto Classification", shortLabel: "Auto Class." },
  { value: "intent_classify", label: "意圖分類", shortLabel: "意圖" },
] as const;

const LABEL_BY_VALUE: Record<string, string> = Object.fromEntries(
  USAGE_CATEGORIES.map((c) => [c.value, c.label]),
);

const SHORT_LABEL_BY_VALUE: Record<string, string> = Object.fromEntries(
  USAGE_CATEGORIES.map((c) => [c.value, c.shortLabel]),
);

/** 取完整中文 label；未知值回傳原字串（legacy/typo fallback） */
export function getCategoryLabel(value: string): string {
  return LABEL_BY_VALUE[value] ?? value;
}

/** 取短中文 label（table / chart 用）；未知值回傳原字串 */
export function getCategoryShortLabel(value: string): string {
  return SHORT_LABEL_BY_VALUE[value] ?? value;
}

/** 是否為對話類（計入「對話次數」統計） */
export function isChatType(value: string): boolean {
  return value === "chat_web" || value === "chat_widget" || value === "chat_line";
}
