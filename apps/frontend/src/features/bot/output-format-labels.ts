import type { BotMode, OutputFormat } from "@/types/bot";
import type { StructuredOutputTier } from "@/types/llm-capability";

/** Issue #70 — miss_reply 留空時後端使用的平台預設話術（前端只作 placeholder） */
export const DEFAULT_MISS_REPLY =
  "很抱歉，這個問題不在我的服務範圍內，歡迎換個方式問我。";

/** output_format=json 時的未命中話術 placeholder（話術本身必須是合法 JSON） */
export const DEFAULT_MISS_REPLY_JSON =
  '{"status":"out_of_scope","category":"unclassified","answer":""}';

/** 知識庫問答模式建議的相關度門檻（Milvus COSINE 0–1；平台預設 0.3 偏鬆） */
export const KB_MODE_RECOMMENDED_SCORE_THRESHOLD = 0.5;

export const KB_MODE_THRESHOLD_HINT =
  "知識庫問答模式建議 0.5 以上（Milvus COSINE 相似度 0–1，預設 0.3 偏鬆）；低於門檻直接回未命中話術，不會升級";

export const BOT_MODE_BADGE_LABELS: Record<BotMode, string> = {
  fast: "快速",
  deep: "深度",
  kb: "知識庫",
};

export const OUTPUT_FORMAT_LABELS: Record<
  OutputFormat,
  { label: string; hint: string }
> = {
  text: { label: "一般", hint: "保留 Markdown，交由通路自行呈現" },
  plain_text: {
    label: "純文字（自動移除 Markdown 符號）",
    hint: "適合 LINE / 語音 / 第三方系統直接顯示",
  },
  json: {
    label: "JSON",
    hint: "結構化輸出，可附 JSON schema；結果放在 structured_content",
  },
};

export type CapabilityTone = "success" | "warning" | "danger" | "neutral";

export const STRUCTURED_OUTPUT_TIER_LABELS: Record<
  StructuredOutputTier,
  { label: string; tone: CapabilityTone }
> = {
  native_schema: { label: "原生 schema", tone: "success" },
  json_object: {
    label: "僅保證 JSON，欄位由系統驗證並重試一次",
    tone: "warning",
  },
  prompt_only: { label: "無格式保證，僅靠提示詞", tone: "danger" },
};

export const CAPABILITY_NO_MODEL_LABEL = "請先選擇模型";
export const CAPABILITY_LOADING_LABEL = "查詢能力中…";
export const CAPABILITY_ERROR_LABEL = "無法取得能力資訊";
