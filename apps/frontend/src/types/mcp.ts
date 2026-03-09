export interface McpToolParam {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: unknown;
}

export interface McpToolInfo {
  name: string;
  description: string;
  parameters: McpToolParam[];
}

export interface McpDiscoverResponse {
  server_name: string;
  tools: McpToolInfo[];
  version: string;
}
