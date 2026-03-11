import { useParams, Link } from "react-router-dom";
import { useAdminKnowledgeBases } from "@/hooks/queries/use-admin";
import { useDocuments } from "@/hooks/queries/use-documents";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { ROUTES } from "@/routes/paths";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function AdminKbDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: knowledgeBases, isLoading } = useAdminKnowledgeBases();
  const { data: documents, isLoading: docsLoading } = useDocuments(id!);
  const tenantNameMap = useTenantNameMap();

  const kb = knowledgeBases?.find((k) => k.id === id);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full rounded" />
      </div>
    );
  }

  if (!kb) {
    return (
      <div className="p-6">
        <p className="text-destructive">找不到此知識庫。</p>
      </div>
    );
  }

  const tenantName = tenantNameMap.get(kb.tenant_id) ?? kb.tenant_id.slice(0, 8);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center gap-2">
        <Link
          to={ROUTES.ADMIN_KNOWLEDGE_BASES}
          className="text-sm text-muted-foreground hover:underline"
        >
          所有知識庫
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        <span className="text-sm">{kb.name}</span>
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">{kb.name}</h2>
        <Badge variant="outline">唯讀</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>基本資訊</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
            <div>
              <dt className="text-sm text-muted-foreground">租戶</dt>
              <dd className="mt-1 font-medium">{tenantName}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">文件數</dt>
              <dd className="mt-1 font-medium">{kb.document_count}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">建立時間</dt>
              <dd className="mt-1 font-medium">
                {new Date(kb.created_at).toLocaleDateString("zh-TW")}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">更新時間</dt>
              <dd className="mt-1 font-medium">
                {new Date(kb.updated_at).toLocaleDateString("zh-TW")}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {kb.description && (
        <Card>
          <CardHeader>
            <CardTitle>說明</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>{kb.description}</CardDescription>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>文件列表</CardTitle>
        </CardHeader>
        <CardContent>
          {docsLoading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded" />
              ))}
            </div>
          )}

          {documents && documents.length === 0 && (
            <p className="text-muted-foreground">此知識庫尚無文件。</p>
          )}

          {documents && documents.length > 0 && (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>檔名</TableHead>
                    <TableHead>狀態</TableHead>
                    <TableHead>分塊數</TableHead>
                    <TableHead>品質分數</TableHead>
                    <TableHead>建立時間</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium">
                        {doc.filename}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            doc.status === "processed"
                              ? "default"
                              : doc.status === "failed"
                                ? "destructive"
                                : "secondary"
                          }
                        >
                          {doc.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{doc.chunk_count}</TableCell>
                      <TableCell>
                        {doc.quality_score > 0
                          ? `${(doc.quality_score * 100).toFixed(0)}%`
                          : "-"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(doc.created_at).toLocaleDateString("zh-TW")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
