export interface McpRegistrationToolMeta {
  name: string;
  description: string;
}

export interface McpRegistration {
  id: string;
  name: string;
  description: string;
  transport: "http" | "stdio";
  url: string;
  command: string;
  args: string[];
  required_env: string[];
  available_tools: McpRegistrationToolMeta[];
  version: string;
  scope: "global" | "tenant";
  tenant_ids: string[];
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateMcpServerRequest {
  name: string;
  description?: string;
  transport?: "http" | "stdio";
  url?: string;
  command?: string;
  args?: string[];
  required_env?: string[];
  scope?: string;
  tenant_ids?: string[];
}

export interface UpdateMcpServerRequest extends Partial<CreateMcpServerRequest> {
  is_enabled?: boolean;
  available_tools?: McpRegistrationToolMeta[];
}

export interface DiscoverMcpToolsRequest {
  transport?: "http" | "stdio";
  url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
}

export interface DiscoverMcpToolsResponse {
  tools: McpRegistrationToolMeta[];
  server_name: string;
  version: string;
}

export interface TestConnectionResponse {
  success: boolean;
  latency_ms: number | null;
  error: string | null;
  tools_count: number | null;
}

export interface BotMcpBinding {
  registry_id: string;
  enabled_tools: string[];
  env_values: Record<string, string>;
}
