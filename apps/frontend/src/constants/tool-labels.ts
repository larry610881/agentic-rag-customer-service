// i18n safety-net：backend 已在 tool_calls / ChatResponse 的 ToolCallInfo.label 欄位
// 直接帶 resolve 後的顯示名稱（見 Issue #30 / backend src/application/agent/tool_label_resolver.py）。
// 本檔僅作為 streaming status hint 等「無 ToolCallInfo 物件可讀 label」的場景 fallback。
// 前端不新增 built-in tool 到本表 — 新 tool 的 label 統一交由 backend BUILT_IN_TOOL_DEFAULTS。
export const TOOL_LABELS: Record<string, string> = {
  rag_query: "知識庫查詢",
  query_dm_with_image: "DM 圖卡查詢",
  transfer_to_human_agent: "轉接真人客服",
  search_products: "查詢商品",
  search_courses: "查詢課程",
};

export const getToolLabel = (name: string): string =>
  TOOL_LABELS[name] || name;
