import { useMemo } from "react";
import { useTenants } from "./queries/use-tenants";

export function useTenantNameMap(): Map<string, string> {
  const { data } = useTenants();
  return useMemo(() => {
    const map = new Map<string, string>();
    data?.items?.forEach((t) => map.set(t.id, t.name));
    return map;
  }, [data]);
}
