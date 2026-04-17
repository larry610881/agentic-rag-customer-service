import { AdminToolsTable } from "@/features/admin/components/admin-tools-table";

export default function AdminToolsPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="text-2xl font-semibold">工具權限</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          控制系統內建工具（rag_query / query_dm_with_image /
          transfer_to_human_agent）對哪些租戶開放。Global 表示所有租戶可見；
          Tenant 僅白名單租戶可見。
        </p>
      </div>
      <AdminToolsTable />
    </div>
  );
}
