import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RotateCcw } from "lucide-react";
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
            <TableHead>Collection 名稱</TableHead>
            <TableHead className="text-right">rows</TableHead>
            <TableHead>tenant_id index</TableHead>
            <TableHead>document_id index</TableHead>
            <TableHead>vector index</TableHead>
            <TableHead className="w-[140px]">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {collections.map((col) => {
            const tidIdx = col.indexes.find((i) => i.field === "tenant_id");
            const didIdx = col.indexes.find((i) => i.field === "document_id");
            const vecIdx = col.indexes.find((i) => i.field === "vector");
            return (
              <TableRow key={col.name}>
                <TableCell className="font-mono text-sm">{col.name}</TableCell>
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
