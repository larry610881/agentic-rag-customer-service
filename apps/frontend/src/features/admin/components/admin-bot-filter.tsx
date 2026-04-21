import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAdminBots } from "@/hooks/queries/use-admin";

interface AdminBotFilterProps {
  /** 選的 bot id；undefined = 全部 */
  value: string | undefined;
  onChange: (botId: string | undefined) => void;
  /** 同時依 tenant 限制 bot 列表（admin 切了 tenant 後 bot 才有意義）*/
  tenantId?: string;
  className?: string;
}

export function AdminBotFilter({
  value,
  onChange,
  tenantId,
  className,
}: AdminBotFilterProps) {
  // 直接用 admin 跨租戶 bot list；tenantId 過濾在 backend
  const { data } = useAdminBots(tenantId, 1, 200);
  const bots = data?.items ?? [];

  return (
    <Select
      value={value ?? "all"}
      onValueChange={(v) => onChange(v === "all" ? undefined : v)}
    >
      <SelectTrigger className={className ?? "w-[200px]"}>
        <SelectValue placeholder="選擇 Bot" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">全部 Bot</SelectItem>
        {bots.map((b) => (
          <SelectItem key={b.id} value={b.id}>
            {b.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
