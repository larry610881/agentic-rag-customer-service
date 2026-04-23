import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { ConvSummaryItem } from "@/types/conv-summary";

interface ConvSummaryListProps {
  items: ConvSummaryItem[];
}

export function ConvSummaryList({ items }: ConvSummaryListProps) {
  if (items.length === 0) {
    return (
      <p className="text-muted-foreground text-sm py-6 text-center">
        無對話摘要紀錄
      </p>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>建立時間</TableHead>
            <TableHead>Bot</TableHead>
            <TableHead>Conversation</TableHead>
            <TableHead>摘要</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item, idx) => (
            <TableRow
              key={item.conversation_id ?? `row-${idx}`}
              className="align-top"
            >
              <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                {item.created_at ?? "—"}
              </TableCell>
              <TableCell>
                {item.bot_id ? (
                  <Badge variant="outline" className="text-xs font-mono">
                    {item.bot_id.slice(0, 8)}
                  </Badge>
                ) : (
                  "—"
                )}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {item.conversation_id?.slice(0, 12) ?? "—"}
              </TableCell>
              <TableCell className="max-w-[600px]">
                <p className="text-sm line-clamp-3 whitespace-pre-wrap">
                  {item.summary ?? "(無摘要)"}
                </p>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
