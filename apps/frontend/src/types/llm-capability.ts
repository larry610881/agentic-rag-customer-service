/**
 * Issue #70 — 供應商 × 模型的結構化輸出能力等級。
 * native_schema：A 級，供應商原生支援 JSON schema。
 * json_object：B 級，僅保證合法 JSON，欄位由系統驗證並重試一次。
 * prompt_only：C 級，無格式保證，僅靠提示詞。
 */
export type StructuredOutputTier =
  | "native_schema"
  | "json_object"
  | "prompt_only";

export interface StructuredOutputCapability {
  provider: string;
  model: string;
  tier: StructuredOutputTier;
  note: string;
}
