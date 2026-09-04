import type { BotOutputSchema } from "@/types/bot";

/** Issue #70 — output_format=json 的 JSON schema 範本；新增範本只需在此加一筆 */
export interface OutputSchemaTemplate {
  id: string;
  label: string;
  schema: BotOutputSchema;
}

export const OUTPUT_SCHEMA_TEMPLATES: readonly OutputSchemaTemplate[] = [
  {
    id: "three_way",
    label: "三分流（status / category / answer）",
    schema: {
      type: "object",
      additionalProperties: false,
      required: ["status", "category", "answer"],
      properties: {
        status: { type: "string", enum: ["km", "out_of_scope"] },
        category: {
          type: "string",
          enum: ["product-exhibit", "marketing", "store-ops", "unclassified"],
        },
        answer: { type: "string" },
      },
    },
  },
];

export const OUTPUT_SCHEMA_TEMPLATE_HINT =
  "必填欄位與 enum 都在 schema 裡定義，供應商依能力等級強制或驗證";

/** 序列化成 textarea 用的縮排 JSON 文字 */
export function serializeOutputSchema(schema: BotOutputSchema): string {
  return JSON.stringify(schema, null, 2);
}

/**
 * 從 schema 文字取出頂層 properties 的欄位名；非物件 / 無 properties / 解析失敗回空陣列。
 * 供「通路顯示欄位」下拉選項使用。
 */
export function extractSchemaPropertyNames(text: string): string[] {
  try {
    const parsed: unknown = JSON.parse(text);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return [];
    const props = (parsed as { properties?: unknown }).properties;
    if (!props || typeof props !== "object" || Array.isArray(props)) return [];
    return Object.keys(props as Record<string, unknown>);
  } catch {
    return [];
  }
}
