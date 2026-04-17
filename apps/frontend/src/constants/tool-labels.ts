// NOTE: 與 backend src/domain/agent/built_in_tool.py 的 BUILT_IN_TOOL_DEFAULTS 對齊。
// 這是架構 smell（同一份 label 兩處維護），理想做法是改為透過 GET /api/v1/agent/built-in-tools
// 動態抓 label 並 cache。短期先手動同步文案。
export const TOOL_LABELS: Record<string, string> = {
  // Built-in tools（來源：backend BUILT_IN_TOOL_DEFAULTS）
  rag_query: "知識庫查詢",
  query_dm_with_image: "DM 圖卡查詢",
  transfer_to_human_agent: "轉接真人客服",
  // MCP tools（範例：窩廚房）
  search_products: "查詢商品",
  search_courses: "查詢課程",
};

export const getToolLabel = (name: string): string =>
  TOOL_LABELS[name] || name;
