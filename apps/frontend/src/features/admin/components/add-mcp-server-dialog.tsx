import { useState } from "react";
import { Loader2, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useCreateMcpRegistration,
  useDiscoverMcpRegistryTools,
} from "@/hooks/queries/use-mcp-registry";
import type { McpRegistrationToolMeta } from "@/types/mcp-registry";

type Transport = "http" | "stdio";

interface DiscoveredState {
  tools: McpRegistrationToolMeta[];
  serverName: string;
  version: string;
}

export function AddMcpServerDialog() {
  const [open, setOpen] = useState(false);
  const [transport, setTransport] = useState<Transport>("http");
  const [url, setUrl] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [discovered, setDiscovered] = useState<DiscoveredState | null>(null);

  const discoverMutation = useDiscoverMcpRegistryTools();
  const createMutation = useCreateMcpRegistration();

  const resetForm = () => {
    setTransport("http");
    setUrl("");
    setCommand("");
    setArgs("");
    setName("");
    setDescription("");
    setDiscovered(null);
  };

  const handleDiscover = () => {
    if (transport === "http" && !url) {
      toast.error("請輸入 Server URL");
      return;
    }
    if (transport === "stdio" && !command) {
      toast.error("請輸入執行指令");
      return;
    }

    const payload =
      transport === "http"
        ? { transport: "http" as const, url }
        : {
            transport: "stdio" as const,
            command,
            args: args
              .split(/\s+/)
              .filter(Boolean),
          };

    discoverMutation.mutate(payload, {
      onSuccess: (result) => {
        setDiscovered({
          tools: result.tools,
          serverName: result.server_name,
          version: result.version,
        });
        if (!name) {
          setName(result.server_name);
        }
        toast.success(`探索到 ${result.tools.length} 個 Tools`);
      },
      onError: () => {
        toast.error("無法連線 MCP Server，請確認位址是否正確");
      },
    });
  };

  const handleSave = () => {
    if (!name.trim()) {
      toast.error("請輸入 Server 名稱");
      return;
    }

    const payload =
      transport === "http"
        ? {
            name: name.trim(),
            description: description.trim() || undefined,
            transport: "http" as const,
            url,
          }
        : {
            name: name.trim(),
            description: description.trim() || undefined,
            transport: "stdio" as const,
            command,
            args: args.split(/\s+/).filter(Boolean),
          };

    createMutation.mutate(payload, {
      onSuccess: () => {
        toast.success(`已註冊 ${name}`);
        resetForm();
        setOpen(false);
      },
      onError: () => {
        toast.error("註冊失敗");
      },
    });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) resetForm();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          新增 MCP Server
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>新增 MCP Server</DialogTitle>
          <DialogDescription>
            設定傳輸方式與連線資訊，探索可用 Tools 後儲存。
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          {/* Transport select */}
          <div className="flex flex-col gap-2">
            <Label>傳輸方式</Label>
            <Select
              value={transport}
              onValueChange={(v) => {
                setTransport(v as Transport);
                setDiscovered(null);
              }}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="http">HTTP</SelectItem>
                <SelectItem value="stdio">Stdio</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Connection info */}
          {transport === "http" ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor="mcp-server-url">Server URL</Label>
              <Input
                id="mcp-server-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="http://localhost:9000/mcp"
              />
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                <Label htmlFor="mcp-server-command">執行指令</Label>
                <Input
                  id="mcp-server-command"
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="npx"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="mcp-server-args">參數（空格分隔）</Label>
                <Input
                  id="mcp-server-args"
                  value={args}
                  onChange={(e) => setArgs(e.target.value)}
                  placeholder="-y @modelcontextprotocol/server-sqlite"
                />
              </div>
            </>
          )}

          {/* Discover button */}
          <Button
            type="button"
            variant="outline"
            onClick={handleDiscover}
            disabled={discoverMutation.isPending}
          >
            {discoverMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Search className="mr-2 h-4 w-4" />
            )}
            探索 Tools
          </Button>

          {/* Discovered tools */}
          {discovered && (
            <div className="flex flex-col gap-3 rounded-md border p-3 bg-muted/30">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium">
                  {discovered.serverName}
                </span>
                {discovered.version && (
                  <Badge variant="outline" className="text-xs">
                    v{discovered.version}
                  </Badge>
                )}
                <Badge variant="secondary" className="text-xs">
                  {discovered.tools.length} tools
                </Badge>
              </div>
              <div className="flex flex-col gap-1">
                {discovered.tools.map((tool) => (
                  <div key={tool.name} className="text-sm">
                    <span className="font-mono text-xs font-medium">
                      {tool.name}
                    </span>
                    {tool.description && (
                      <span className="ml-2 text-muted-foreground text-xs">
                        {tool.description.length > 80
                          ? tool.description.slice(0, 80) + "..."
                          : tool.description}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Name & Description */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="mcp-server-name">名稱</Label>
            <Input
              id="mcp-server-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="MCP Server 名稱"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="mcp-server-description">描述（選填）</Label>
            <Textarea
              id="mcp-server-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="簡要描述此 Server 的功能"
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              resetForm();
              setOpen(false);
            }}
          >
            取消
          </Button>
          <Button
            onClick={handleSave}
            disabled={createMutation.isPending || !name.trim()}
          >
            {createMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            儲存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
