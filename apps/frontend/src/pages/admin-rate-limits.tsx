import { useState } from "react";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import {
  useRateLimits,
  useUpdateRateLimit,
  useSystemRateLimits,
  useUpdateSystemRateLimit,
  type RateLimitConfig,
} from "@/hooks/queries/use-rate-limits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

const GROUP_LABELS: Record<string, string> = {
  feedback: "回饋",
  rag: "RAG",
  general: "一般",
  webhook: "Webhook",
};

function RateLimitRow({
  config,
  tenantId,
}: {
  config: RateLimitConfig;
  tenantId: string;
}) {
  const [rpm, setRpm] = useState(config.requests_per_minute);
  const [perUser, setPerUser] = useState(
    config.per_user_requests_per_minute ?? "",
  );
  const mutation = useUpdateRateLimit(tenantId);

  const isDirty =
    rpm !== config.requests_per_minute ||
    (perUser === ""
      ? config.per_user_requests_per_minute !== null
      : Number(perUser) !== config.per_user_requests_per_minute);

  const handleSave = () => {
    mutation.mutate(
      {
        endpoint_group: config.endpoint_group,
        requests_per_minute: rpm,
        burst_size: config.burst_size,
        per_user_requests_per_minute:
          perUser === "" ? null : Number(perUser),
      },
      {
        onSuccess: () =>
          toast.success(`${GROUP_LABELS[config.endpoint_group] ?? config.endpoint_group} 速率限制已更新`),
        onError: () =>
          toast.error("儲存失敗"),
      },
    );
  };

  return (
    <TableRow>
      <TableCell className="font-medium">
        {GROUP_LABELS[config.endpoint_group] ?? config.endpoint_group}
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-28"
          value={rpm}
          onChange={(e) => setRpm(Number(e.target.value))}
        />
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-28"
          value={perUser}
          placeholder="—"
          onChange={(e) =>
            setPerUser(e.target.value === "" ? "" : Number(e.target.value))
          }
        />
      </TableCell>
      <TableCell>
        <Button
          size="sm"
          disabled={!isDirty || mutation.isPending}
          onClick={handleSave}
        >
          {mutation.isPending ? "儲存中…" : "儲存"}
        </Button>
      </TableCell>
    </TableRow>
  );
}

function SystemRateLimitRow({ config }: { config: RateLimitConfig }) {
  const [rpm, setRpm] = useState(config.requests_per_minute);
  const [perUser, setPerUser] = useState(
    config.per_user_requests_per_minute ?? "",
  );
  const mutation = useUpdateSystemRateLimit();

  const isDirty =
    rpm !== config.requests_per_minute ||
    (perUser === ""
      ? config.per_user_requests_per_minute !== null
      : Number(perUser) !== config.per_user_requests_per_minute);

  const handleSave = () => {
    mutation.mutate(
      {
        endpoint_group: config.endpoint_group,
        requests_per_minute: rpm,
        burst_size: config.burst_size,
        per_user_requests_per_minute:
          perUser === "" ? null : Number(perUser),
      },
      {
        onSuccess: () =>
          toast.success(`${GROUP_LABELS[config.endpoint_group] ?? config.endpoint_group} 系統預設已更新`),
        onError: () =>
          toast.error("儲存失敗"),
      },
    );
  };

  return (
    <TableRow>
      <TableCell className="font-medium">
        {GROUP_LABELS[config.endpoint_group] ?? config.endpoint_group}
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-28"
          value={rpm}
          onChange={(e) => setRpm(Number(e.target.value))}
        />
      </TableCell>
      <TableCell>
        <Input
          type="number"
          className="w-28"
          value={perUser}
          placeholder="—"
          onChange={(e) =>
            setPerUser(e.target.value === "" ? "" : Number(e.target.value))
          }
        />
      </TableCell>
      <TableCell>
        <Button
          size="sm"
          disabled={!isDirty || mutation.isPending}
          onClick={handleSave}
        >
          {mutation.isPending ? "儲存中…" : "儲存"}
        </Button>
      </TableCell>
    </TableRow>
  );
}

function RateLimitTable({ children }: { children: React.ReactNode }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>端點群組</TableHead>
          <TableHead>每分鐘請求數</TableHead>
          <TableHead>每用戶每分鐘</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>{children}</TableBody>
    </Table>
  );
}

function SystemDefaultsTab() {
  const { data, isLoading } = useSystemRateLimits();

  if (isLoading) {
    return <p className="text-muted-foreground">載入中…</p>;
  }

  return (
    <RateLimitTable>
      {data?.map((cfg) => (
        <SystemRateLimitRow key={cfg.endpoint_group} config={cfg} />
      ))}
    </RateLimitTable>
  );
}

function TenantOverridesTab() {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const { data, isLoading } = useRateLimits(tenantId);

  return (
    <div className="space-y-4">
      <AdminTenantFilter value={tenantId} onChange={setTenantId} />
      {!tenantId ? (
        <p className="text-muted-foreground">請選擇租戶以查看速率限制設定</p>
      ) : isLoading ? (
        <p className="text-muted-foreground">載入中…</p>
      ) : (
        <RateLimitTable>
          {data?.map((cfg) => (
            <RateLimitRow
              key={cfg.endpoint_group}
              config={cfg}
              tenantId={tenantId}
            />
          ))}
        </RateLimitTable>
      )}
    </div>
  );
}

export default function AdminRateLimitsPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">速率限制</h1>
        <p className="text-muted-foreground">
          管理系統預設與各租戶的 API 速率限制設定
        </p>
      </div>

      <Tabs defaultValue="system">
        <TabsList>
          <TabsTrigger value="system">系統預設</TabsTrigger>
          <TabsTrigger value="tenant">租戶設定</TabsTrigger>
        </TabsList>
        <TabsContent value="system" className="mt-4">
          <SystemDefaultsTab />
        </TabsContent>
        <TabsContent value="tenant" className="mt-4">
          <TenantOverridesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
