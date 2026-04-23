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
  { value: "ocr", label: "文件 OCR 解析", shortLabel: "OCR" },
  { value: "embedding", label: "向量嵌入", shortLabel: "Embedding" },
  { value: "guard", label: "提示詞防護", shortLabel: "Guard" },
  { value: "rerank", label: "LLM 重排", shortLabel: "Rerank" },
  { value: "contextual_retrieval", label: "上下文增強檢索", shortLabel: "上下文增強" },
  { value: "pdf_rename", label: "PDF 子頁命名", shortLabel: "PDF 命名" },
  { value: "auto_classification", label: "自動分類", shortLabel: "自動分類" },
  { value: "intent_classify", label: "意圖分類", shortLabel: "意圖" },
  // S-Gov.6b: 對話 LLM 摘要（cron 行為，POC 預設不計入 quota）
  { value: "conversation_summary", label: "對話 LLM 摘要", shortLabel: "摘要" },
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
