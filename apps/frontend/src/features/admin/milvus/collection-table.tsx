import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RotateCcw, Pencil } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CollectionInfo } from "@/types/milvus";

interface CollectionTableProps {
  collections: CollectionInfo[];
  onRebuildIndex: (name: string) => void;
  rebuildingName?: string | null;
}

export function CollectionTable({
  collections,
  onRebuildIndex,
  rebuildingName,
}: CollectionTableProps) {
  if (collections.length === 0) {
    return (
      <p className="text-muted-foreground text-sm py-6 text-center">
        無 Milvus collection
      </p>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>歸屬 / Collection</TableHead>
            <TableHead className="text-right">rows</TableHead>
            <TableHead>tenant_id index</TableHead>
            <TableHead>document_id index</TableHead>
            <TableHead>vector index</TableHead>
            <TableHead className="w-[260px]">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {collections.map((col) => {
            const tidIdx = col.indexes.find((i) => i.field === "tenant_id");
            const didIdx = col.indexes.find((i) => i.field === "document_id");
            const vecIdx = col.indexes.find((i) => i.field === "vector");
            return (
              <TableRow key={col.name}>
                <TableCell className="text-sm">
                  {col.kb_name ? (
                    <div className="space-y-0.5">
                      <div className="font-medium flex items-center gap-2">
                        <span>{col.kb_name}</span>
                        {col.tenant_name && (
                          <Badge variant="outline" className="text-xs">
                            {col.tenant_name}
                          </Badge>
                        )}
                      </div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {col.name}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-0.5">
                      <div className="text-muted-foreground italic">
                        {col.name.startsWith("kb_") ? "(KB 已刪除)" : "系統"}
                      </div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {col.name}
                      </div>
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {col.row_count.toLocaleString()}
                </TableCell>
                <TableCell>
                  <IndexBadge type={tidIdx?.index_type} />
                </TableCell>
                <TableCell>
                  <IndexBadge type={didIdx?.index_type} />
                </TableCell>
                <TableCell>
                  <IndexBadge type={vecIdx?.index_type} />
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {col.kb_id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        asChild
                        title="到 KB Studio 編輯 chunks"
                      >
                        <Link
                          to={`/admin/kb-studio/${col.kb_id}?tab=chunks`}
                        >
                          <Pencil className="h-3 w-3 mr-1" />
                          編輯 chunks
                        </Link>
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={rebuildingName === col.name}
                      onClick={() => onRebuildIndex(col.name)}
                    >
                      <RotateCcw className="h-3 w-3 mr-1" />
                      {rebuildingName === col.name
                        ? "重建中..."
                        : "重建 index"}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function IndexBadge({ type }: { type?: string }) {
  if (!type || type === "(empty)" || type === "none") {
    return (
      <Badge variant="destructive" className="text-xs">
        未建 ⚠️
      </Badge>
    );
  }
  if (type === "INVERTED" || type === "AUTOINDEX") {
    return (
      <Badge variant="default" className="text-xs">
        {type}
      </Badge>
    );
  }
  return <Badge variant="outline" className="text-xs">{type}</Badge>;
}
