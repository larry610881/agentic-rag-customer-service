"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuthStore } from "@/stores/use-auth-store";
import { useTenants } from "@/hooks/queries/use-tenants";
import { useEffect } from "react";

export function TenantSelector() {
  const { tenantId, setTenantId, setTenants } = useAuthStore();
  const { data: tenants } = useTenants();

  useEffect(() => {
    if (tenants && tenants.length > 0) {
      setTenants(tenants);
      if (!tenantId) {
        setTenantId(tenants[0].id);
      }
    }
  }, [tenants, tenantId, setTenantId, setTenants]);

  if (!tenants || tenants.length === 0) {
    return null;
  }

  return (
    <Select value={tenantId ?? undefined} onValueChange={setTenantId}>
      <SelectTrigger className="w-48" aria-label="選擇租戶">
        <SelectValue placeholder="選擇租戶" />
      </SelectTrigger>
      <SelectContent>
        {tenants.map((tenant) => (
          <SelectItem key={tenant.id} value={tenant.id}>
            {tenant.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
