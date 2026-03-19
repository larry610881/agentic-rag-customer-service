import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTenants } from "@/hooks/queries/use-tenants";

const SYSTEM_TENANT_ID = "00000000-0000-0000-0000-000000000000";

interface AdminTenantFilterProps {
  value: string | undefined;
  onChange: (tenantId: string | undefined) => void;
  className?: string;
}

export function AdminTenantFilter({ value, onChange, className }: AdminTenantFilterProps) {
  const { data } = useTenants();

  const realTenants = data?.items?.filter((t) => t.id !== SYSTEM_TENANT_ID) ?? [];

  return (
    <Select
      value={value ?? "all"}
      onValueChange={(v) => onChange(v === "all" ? undefined : v)}
    >
      <SelectTrigger className={className ?? "w-[200px]"}>
        <SelectValue placeholder="選擇租戶" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">全部租戶</SelectItem>
        {realTenants.map((t) => (
          <SelectItem key={t.id} value={t.id}>
            {t.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
