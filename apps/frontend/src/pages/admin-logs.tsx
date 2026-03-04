import { RequestLogsTable } from "@/features/admin/components/request-logs-table";

export default function AdminLogsPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">系統日誌</h1>
        <p className="text-muted-foreground">
          查看每個 API 請求的完整 trace 耗時
        </p>
      </div>
      <RequestLogsTable />
    </div>
  );
}
