import { Badge } from "@/components/ui/badge";
import { useDocuments } from "@/hooks/queries/use-documents";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface OverviewTabProps {
  kbId: string;
}

export function OverviewTab({ kbId }: OverviewTabProps) {
  const { data: pagedData, isLoading } = useDocuments(kbId);
  const documents = pagedData?.items ?? [];

  return (
    <div className="space-y-4">
      <section>
        <h3 className="text-sm font-semibold mb-2">文件統計</h3>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="文件數" value={documents.length} />
          <StatCard
            label="處理中"
            value={
              documents.filter(
                (d) => d.status === "pending" || d.status === "processing",
              ).length
            }
          />
          <StatCard
            label="失敗"
            value={documents.filter((d) => d.status === "failed").length}
            accent={
              documents.filter((d) => d.status === "failed").length > 0
                ? "warn"
                : "ok"
            }
          />
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold mb-2">最近文件</h3>
        {isLoading ? (
          <p className="text-muted-foreground text-sm">載入中...</p>
        ) : documents.length === 0 ? (
          <p className="text-muted-foreground text-sm">尚無文件</p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>檔名</TableHead>
                  <TableHead>狀態</TableHead>
                  <TableHead className="text-right">chunks</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.slice(0, 20).map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="truncate max-w-[400px]">
                      {d.filename}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={d.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      {d.chunk_count ?? 0}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent = "ok",
}: {
  label: string;
  value: number;
  accent?: "ok" | "warn";
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div
        className={
          accent === "warn"
            ? "text-2xl font-bold text-amber-600"
            : "text-2xl font-bold"
        }
      >
        {value}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "processed") {
    return <Badge variant="default">已處理</Badge>;
  }
  if (status === "failed") {
    return <Badge variant="destructive">失敗</Badge>;
  }
  if (status === "processing") {
    return <Badge variant="secondary">處理中</Badge>;
  }
  return <Badge variant="outline">{status}</Badge>;
}
