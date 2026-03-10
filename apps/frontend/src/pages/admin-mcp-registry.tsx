import { McpRegistryTable } from "@/features/admin/components/mcp-registry-table";
import { AddMcpServerDialog } from "@/features/admin/components/add-mcp-server-dialog";

export default function AdminMcpRegistryPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">MCP 工具庫</h2>
          <p className="text-sm text-muted-foreground mt-1">
            集中管理 MCP Server 註冊，Bot 可從工具庫中選擇並綁定。
          </p>
        </div>
        <AddMcpServerDialog />
      </div>
      <McpRegistryTable />
    </div>
  );
}
