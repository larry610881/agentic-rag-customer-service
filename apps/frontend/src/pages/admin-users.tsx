import { UserTable } from "@/features/admin/components/user-table";

export default function AdminUsersPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <h2 className="text-2xl font-semibold">帳號管理</h2>
      <UserTable />
    </div>
  );
}
