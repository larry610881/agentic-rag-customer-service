import { useState, useCallback } from "react";
import { type UseFormRegister } from "react-hook-form";
import { Search, Loader2, X, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useMcpRegistry,
  useMcpRegistryAccessible,
} from "@/hooks/queries/use-mcp-registry";
import { useAuthStore } from "@/stores/use-auth-store";
import { useDiscoverMcpTools } from "@/hooks/queries/use-mcp";
import type { McpRegistration } from "@/types/mcp-registry";
import type { McpServerConfig } from "@/types/bot";
import type { McpToolInfo } from "@/types/mcp";

interface McpBindingsSectionProps {
  mcpServers: McpServerConfig[];
  onMcpServersChange: (servers: McpServerConfig[]) => void;
  serverToolsMap: Record<string, McpToolInfo[]>;
  setServerToolsMap: React.Dispatch<
    React.SetStateAction<Record<string, McpToolInfo[]>>
  >;
  registerMaxToolCalls: ReturnType<UseFormRegister<{ max_tool_calls: number }>>;
  maxToolCallsError?: string;
}

export function McpBindingsSection({
  mcpServers,
  onMcpServersChange,
  serverToolsMap,
  setServerToolsMap,
  registerMaxToolCalls,
  maxToolCallsError,
}: McpBindingsSectionProps) {
  const tenantId = useAuthStore((s) => s.tenantId);
  const { data: registeredServers } = useMcpRegistryAccessible(
    tenantId ?? undefined,
  );
  const discoverMcp = useDiscoverMcpTools();

  const [mode, setMode] = useState<"registry" | "manual">("registry");
  const [mcpUrlInput, setMcpUrlInput] = useState("");
  const [expandedServers, setExpandedServers] = useState<Set<string>>(
    new Set(),
  );

  const toggleExpanded = (key: string) => {
    setExpandedServers((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleAddFromRegistry = useCallback(
    (server: McpRegistration) => {
      const allToolNames = server.available_tools.map((t) => t.name);
      const isStdio = server.transport === "stdio";
      if (mcpServers.some((s) => (isStdio ? s.command === server.command : s.url === server.url))) {
        toast.error("此 Server 已綁定");
        return;
      }
      const newServer: McpServerConfig = {
        url: isStdio ? "" : server.url,
        name: server.name,
        enabled_tools: allToolNames,
        tools: server.available_tools.map((t) => ({
          name: t.name,
          description: t.description,
        })),
        version: server.version ?? "",
        ...(isStdio && {
          transport: "stdio" as const,
          command: server.command ?? "",
          args: server.args ?? [],
        }),
        ...(!isStdio && { transport: "http" as const }),
      };
      onMcpServersChange([...mcpServers, newServer]);
      const mapKey = isStdio ? server.command ?? server.name : server.url;
      setServerToolsMap((prev) => ({
        ...prev,
        [mapKey]: server.available_tools.map((t) => ({
          name: t.name,
          description: t.description,
          parameters: [],
        })),
      }));
      toast.success(
        `已綁定 ${server.name}（${allToolNames.length} 個 Tools）`,
      );
    },
    [mcpServers, onMcpServersChange, setServerToolsMap],
  );

  const handleDiscoverAndAdd = useCallback(async () => {
    if (!mcpUrlInput) {
      toast.error("請先輸入 MCP Server URL");
      return;
    }
    if (mcpServers.some((s) => s.url === mcpUrlInput)) {
      toast.error("此 Server 已綁定");
      return;
    }
    try {
      const result = await discoverMcp.mutateAsync(mcpUrlInput);
      const allToolNames = result.tools.map((t) => t.name);
      const newServer: McpServerConfig = {
        url: mcpUrlInput,
        name: result.server_name,
        enabled_tools: allToolNames,
        tools: result.tools.map((t) => ({
          name: t.name,
          description: t.description,
        })),
        version: result.version ?? "",
      };
      onMcpServersChange([...mcpServers, newServer]);
      setServerToolsMap((prev) => ({
        ...prev,
        [mcpUrlInput]: result.tools,
      }));
      setMcpUrlInput("");
      toast.success(
        `已新增 ${result.server_name}（${result.tools.length} 個 Tools）`,
      );
    } catch {
      toast.error("無法連線 MCP Server");
    }
  }, [mcpUrlInput, mcpServers, discoverMcp, onMcpServersChange, setServerToolsMap]);

  const handleRemoveServer = useCallback(
    (url: string) => {
      onMcpServersChange(mcpServers.filter((s) => s.url !== url));
      setServerToolsMap((prev) => {
        const next = { ...prev };
        delete next[url];
        return next;
      });
    },
    [mcpServers, onMcpServersChange, setServerToolsMap],
  );

  const handleToggleTool = useCallback(
    (serverUrl: string, toolName: string, checked: boolean) => {
      onMcpServersChange(
        mcpServers.map((s) => {
          if (s.url !== serverUrl) return s;
          const tools = checked
            ? [...s.enabled_tools, toolName]
            : s.enabled_tools.filter((t) => t !== toolName);
          return { ...s, enabled_tools: tools };
        }),
      );
    },
    [mcpServers, onMcpServersChange],
  );

  const availableServers = (registeredServers ?? []).filter(
    (rs) =>
      rs.is_enabled && !mcpServers.some((ms) => ms.url === rs.url),
  );

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">MCP 設定</h3>
      <p className="text-sm text-muted-foreground">
        從工具庫選擇已註冊的 MCP Server，或手動輸入 URL 綁定。
      </p>

      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant={mode === "registry" ? "default" : "outline"}
          size="sm"
          onClick={() => setMode("registry")}
        >
          從工具庫選擇
        </Button>
        <Button
          type="button"
          variant={mode === "manual" ? "default" : "outline"}
          size="sm"
          onClick={() => setMode("manual")}
        >
          手動輸入 URL
        </Button>
      </div>

      {/* Registry mode */}
      {mode === "registry" && (
        <div className="flex flex-col gap-2">
          <Label>選擇已註冊的 MCP Server</Label>
          {availableServers.length > 0 ? (
            <div className="flex flex-col gap-2">
              {availableServers.map((server) => (
                <div
                  key={server.id}
                  className="flex items-center justify-between rounded-md border p-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{server.name}</span>
                    <Badge
                      variant={
                        server.transport === "http" ? "default" : "secondary"
                      }
                      className="text-xs"
                    >
                      {server.transport.toUpperCase()}
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {server.available_tools.length} tools
                    </Badge>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleAddFromRegistry(server)}
                  >
                    綁定
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {registeredServers && registeredServers.length > 0
                ? "所有已啟用的 Server 都已綁定。"
                : "尚無已註冊的 MCP Server。請至「MCP 工具庫」頁面新增。"}
            </p>
          )}
        </div>
      )}

      {/* Manual URL mode (legacy) */}
      {mode === "manual" && (
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-mcp-url-input">新增 MCP Server</Label>
          <div className="flex gap-2">
            <Input
              id="bot-mcp-url-input"
              value={mcpUrlInput}
              onChange={(e) => setMcpUrlInput(e.target.value)}
              placeholder="例如：http://localhost:9000/mcp"
              className="flex-1"
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleDiscoverAndAdd}
              disabled={discoverMcp.isPending || !mcpUrlInput}
            >
              {discoverMcp.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Search className="mr-2 h-4 w-4" />
              )}
              探索 Tools
            </Button>
          </div>
        </div>
      )}

      {/* Bound MCP Server cards */}
      {mcpServers.length > 0 && (
        <div className="flex flex-col gap-3">
          <Label>已綁定的 MCP Servers</Label>
          {mcpServers.map((server) => {
            const toolsMeta = serverToolsMap[server.url] ?? [];
            const isExpanded = expandedServers.has(server.url);
            return (
              <div key={server.url} className="rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    className="flex items-center gap-2"
                    onClick={() => toggleExpanded(server.url)}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                    <span className="font-medium text-sm">{server.name}</span>
                    {server.version && (
                      <span className="text-xs text-muted-foreground">
                        v{server.version}
                      </span>
                    )}
                    <Badge variant="outline" className="text-xs">
                      {server.enabled_tools.length}/
                      {toolsMeta.length || server.enabled_tools.length} tools
                    </Badge>
                  </button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => handleRemoveServer(server.url)}
                    aria-label={`移除 ${server.name}`}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                {isExpanded && (
                  <div className="flex flex-col gap-1.5 mt-2 ml-6">
                    {/* Select All / Deselect All */}
                    {(() => {
                      const allNames = toolsMeta.length > 0
                        ? toolsMeta.map((t) => t.name)
                        : server.enabled_tools;
                      const allSelected = allNames.length > 0 && allNames.every((n) => server.enabled_tools.includes(n));
                      return (
                        <button
                          type="button"
                          className="text-xs text-primary hover:underline self-start mb-1"
                          onClick={() => {
                            const serverKey = server.transport === "stdio" ? server.command ?? server.name : server.url;
                            const updated = mcpServers.map((s) => {
                              const sKey = s.transport === "stdio" ? s.command ?? s.name : s.url;
                              if (sKey !== serverKey) return s;
                              return { ...s, enabled_tools: allSelected ? [] : [...allNames] };
                            });
                            onMcpServersChange(updated);
                          }}
                        >
                          {allSelected ? "取消全選" : "全選"}
                        </button>
                      );
                    })()}
                    {toolsMeta.length > 0
                      ? toolsMeta.map((tool) => (
                          <label
                            key={tool.name}
                            className="flex items-start gap-2 text-sm"
                          >
                            <input
                              type="checkbox"
                              checked={server.enabled_tools.includes(tool.name)}
                              onChange={(e) =>
                                handleToggleTool(
                                  server.url,
                                  tool.name,
                                  e.target.checked,
                                )
                              }
                              className="mt-0.5 rounded border-input"
                            />
                            <div>
                              <span className="font-mono text-xs font-medium">
                                {tool.name}
                              </span>
                              <span className="ml-2 text-muted-foreground">
                                {tool.description.length > 60
                                  ? tool.description.slice(0, 60) + "..."
                                  : tool.description}
                              </span>
                            </div>
                          </label>
                        ))
                      : server.enabled_tools.map((toolName) => (
                          <label
                            key={toolName}
                            className="flex items-center gap-2 text-sm"
                          >
                            <input
                              type="checkbox"
                              checked
                              onChange={(e) =>
                                handleToggleTool(
                                  server.url,
                                  toolName,
                                  e.target.checked,
                                )
                              }
                              className="rounded border-input"
                            />
                            <span className="font-mono text-xs font-medium">
                              {toolName}
                            </span>
                          </label>
                        ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Max Tool Calls */}
      <div className="flex flex-col gap-2">
        <Label htmlFor="bot-max-tool-calls">最大 Tool 呼叫次數（1-20）</Label>
        <Input
          id="bot-max-tool-calls"
          type="number"
          min="1"
          max="20"
          className="w-32"
          {...registerMaxToolCalls}
        />
        {maxToolCallsError && (
          <p className="text-sm text-destructive">{maxToolCallsError}</p>
        )}
      </div>
    </section>
  );
}
