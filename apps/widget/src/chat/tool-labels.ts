const TOOL_LABELS: Record<string, string> = {
  rag_query: "查詢知識庫",
  search_products: "查詢商品",
  search_courses: "查詢課程",
};

export const getToolLabel = (name: string): string =>
  TOOL_LABELS[name] || name;

export const getStatusHint = (status: string): string => {
  if (status.endsWith("_executing")) {
    const toolName = status.replace("_executing", "");
    return `\u{1f50d} ${getToolLabel(toolName)} 使用中...`;
  }
  if (status.endsWith("_done")) {
    const toolName = status.replace("_done", "");
    return `\u2705 ${getToolLabel(toolName)} 完成`;
  }
  if (status === "react_thinking") return "\u{1f4ad} 小編正在思考中...";
  if (status === "llm_generating") return "\u{270d}\u{fe0f} 小編努力回覆中...";
  return "";
};
