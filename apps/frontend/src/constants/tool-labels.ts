export const TOOL_LABELS: Record<string, string> = {
  rag_query: "查詢知識庫",
  search_products: "查詢商品",
  search_courses: "查詢課程",
};

export const getToolLabel = (name: string): string =>
  TOOL_LABELS[name] || name;
