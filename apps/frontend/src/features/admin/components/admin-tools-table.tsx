import { useState } from "react";
import { Loader2, Settings } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  useAdminTools,
  type AdminTool,
} from "@/hooks/queries/use-admin-tools";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { useTenants } from "@/hooks/queries/use-tenants";

import { ToolScopeDialog } from "./tool-scope-dialog";

function ScopeCell({
  tool,
  totalTenants,
}: {
  tool: AdminTool;
  totalTenants: number;
}) {
  const tenantNames = useTenantNameMap();
  if (tool.scope === "global") {
    return <Badge variant="secondary">Global</Badge>;
  }
  const labels = tool.tenant_ids
    .map((id) => tenantNames.get(id) ?? id.slice(0, 8))
    .join(", ");
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="cursor-help">
          Tenant · {tool.tenant_ids.length}/{totalTenants}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>{labels || "未指定租戶"}</TooltipContent>
    </Tooltip>
  );
}

export const AdminToolsTable = () => {
  const { data: tools, isLoading, isError, error } = useAdminTools();
  const { data: tenantsData } = useTenants(1, 100);
  const [editing, setEditing] = useState<AdminTool | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> 載入中...
      </div>
    );
  }

  if (isError) {
    return (
      <p className="text-sm text-destructive">
        載入失敗：{error instanceof Error ? error.message : "未知錯誤"}
      </p>
    );
  }

  if (!tools || tools.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        目前沒有任何 built-in tool。請檢查後端啟動 seed 是否成功。
      </p>
    );
  }

  const totalTenants = tenantsData?.items?.length ?? 0;

  return (
    <TooltipProvider>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>名稱</TableHead>
            <TableHead>顯示名</TableHead>
            <TableHead>需要知識庫</TableHead>
            <TableHead>可見範圍</TableHead>
            <TableHead className="w-[80px] text-right">動作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tools.map((tool) => (
            <TableRow key={tool.name}>
              <TableCell className="font-mono text-xs">{tool.name}</TableCell>
              <TableCell>{tool.label}</TableCell>
              <TableCell>
                {tool.requires_kb ? (
                  <Badge variant="outline">是</Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">否</span>
                )}
              </TableCell>
              <TableCell>
                <ScopeCell tool={tool} totalTenants={totalTenants} />
              </TableCell>
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`設定 ${tool.label}`}
                  onClick={() => {
                    setEditing(tool);
                    setDialogOpen(true);
                  }}
                >
                  <Settings className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <ToolScopeDialog
        tool={editing}
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) setEditing(null);
        }}
      />
    </TooltipProvider>
  );
};
