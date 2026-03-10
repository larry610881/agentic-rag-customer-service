import { useState } from "react";
import { Loader2, Trash2, Wifi } from "lucide-react";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  useMcpRegistry,
  useUpdateMcpRegistration,
  useDeleteMcpRegistration,
  useTestMcpConnection,
} from "@/hooks/queries/use-mcp-registry";
import type { McpRegistration } from "@/types/mcp-registry";

export function McpRegistryTable() {
  const { data: servers, isLoading, isError } = useMcpRegistry();
  const updateMutation = useUpdateMcpRegistration();
  const deleteMutation = useDeleteMcpRegistration();
  const testMutation = useTestMcpConnection();
  const [testingId, setTestingId] = useState<string | null>(null);

  const handleToggleEnabled = (server: McpRegistration) => {
    updateMutation.mutate(
      { id: server.id, data: { is_enabled: !server.is_enabled } },
      {
        onSuccess: () => {
          toast.success(
            `${server.name} 已${server.is_enabled ? "停用" : "啟用"}`,
          );
        },
        onError: () => {
          toast.error("更新失敗");
        },
      },
    );
  };

  const handleTestConnection = (server: McpRegistration) => {
    setTestingId(server.id);
    testMutation.mutate(server.id, {
      onSuccess: (result) => {
        if (result.success) {
          toast.success(
            `${server.name} 連線成功（${result.latency_ms}ms, ${result.tools_count} tools）`,
          );
        } else {
          toast.error(`${server.name} 連線失敗：${result.error}`);
        }
      },
      onError: () => {
        toast.error(`${server.name} 連線測試失敗`);
      },
      onSettled: () => {
        setTestingId(null);
      },
    });
  };

  const handleDelete = (server: McpRegistration) => {
    deleteMutation.mutate(server.id, {
      onSuccess: () => {
        toast.success(`已刪除 ${server.name}`);
      },
      onError: () => {
        toast.error("刪除失敗");
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return <p className="text-destructive">載入 MCP 工具庫失敗。</p>;
  }

  if (!servers || servers.length === 0) {
    return (
      <p className="text-muted-foreground py-8 text-center">
        尚未註冊任何 MCP Server。點擊上方「新增 MCP Server」開始註冊。
      </p>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>名稱</TableHead>
            <TableHead>傳輸方式</TableHead>
            <TableHead>位址</TableHead>
            <TableHead className="text-center">Tools</TableHead>
            <TableHead className="text-center">狀態</TableHead>
            <TableHead className="text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {servers.map((server) => (
            <TableRow key={server.id}>
              <TableCell>
                <div className="flex flex-col">
                  <span className="font-medium">{server.name}</span>
                  {server.description && (
                    <span className="text-xs text-muted-foreground truncate max-w-xs">
                      {server.description}
                    </span>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={server.transport === "http" ? "default" : "secondary"}>
                  {server.transport.toUpperCase()}
                </Badge>
              </TableCell>
              <TableCell>
                <code className="text-xs text-muted-foreground">
                  {server.transport === "http"
                    ? server.url
                    : `${server.command} ${server.args.join(" ")}`}
                </code>
              </TableCell>
              <TableCell className="text-center">
                <Tooltip>
                  <TooltipTrigger>
                    <Badge variant="outline">
                      {server.available_tools.length}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-xs">
                    {server.available_tools.length > 0
                      ? server.available_tools.map((t) => t.name).join(", ")
                      : "尚未探索"}
                  </TooltipContent>
                </Tooltip>
              </TableCell>
              <TableCell className="text-center">
                <Switch
                  checked={server.is_enabled}
                  onCheckedChange={() => handleToggleEnabled(server)}
                  aria-label={`切換 ${server.name} 啟用狀態`}
                />
              </TableCell>
              <TableCell className="text-right">
                <div className="flex items-center justify-end gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleTestConnection(server)}
                        disabled={testingId === server.id}
                        aria-label={`測試 ${server.name} 連線`}
                      >
                        {testingId === server.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Wifi className="h-4 w-4" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>測試連線</TooltipContent>
                  </Tooltip>

                  <AlertDialog>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            aria-label={`刪除 ${server.name}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                      </TooltipTrigger>
                      <TooltipContent>刪除</TooltipContent>
                    </Tooltip>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>確定刪除 MCP Server？</AlertDialogTitle>
                        <AlertDialogDescription>
                          確定要刪除「{server.name}」嗎？所有引用此 Server 的 Bot
                          綁定將會失效。此操作無法復原。
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>取消</AlertDialogCancel>
                        <AlertDialogAction
                          variant="destructive"
                          onClick={() => handleDelete(server)}
                        >
                          確定刪除
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
