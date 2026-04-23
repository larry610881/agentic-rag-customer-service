import { useMemo, useState } from "react";
import { useAuthStore } from "@/stores/use-auth-store";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConvSummaryList } from "@/features/admin/conv-summary/conv-summary-list";
import { ConvSummarySearchPanel } from "@/features/admin/conv-summary/conv-summary-search-panel";
import { useConvSummaries } from "@/hooks/queries/use-conv-summaries";
import { cn } from "@/lib/utils";

type Mode = "list" | "search";

export default function AdminConversationSummaryPage() {
  const role = useAuthStore((s) => s.role);
  const ownTenantId = useAuthStore((s) => s.tenantId);

  const [tenantInput, setTenantInput] = useState(
    role === "system_admin" ? "" : ownTenantId ?? "",
  );
  const [botFilter, setBotFilter] = useState("");
  const [mode, setMode] = useState<Mode>("list");

  const tenantId = useMemo(() => tenantInput.trim() || null, [tenantInput]);
  const botId = botFilter.trim() || null;

  const { data, isLoading, error } = useConvSummaries(tenantId, botId);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">對話摘要管理</h1>
        <p className="text-sm text-muted-foreground">
          租戶層 conv_summaries 列表 + 語義搜尋。tenant 必填；bot 可選 filter。
        </p>
      </header>

      <div className="rounded-md border p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label htmlFor="tenant-input">Tenant ID（必填）</Label>
            <Input
              id="tenant-input"
              value={tenantInput}
              onChange={(e) => setTenantInput(e.target.value)}
              placeholder="例：T001"
              disabled={role !== "system_admin"}
            />
          </div>
          <div>
            <Label htmlFor="bot-input">Bot ID（可選）</Label>
            <Input
              id="bot-input"
              value={botFilter}
              onChange={(e) => setBotFilter(e.target.value)}
              placeholder="留空 = 所有 bot"
            />
          </div>
        </div>
        <div className="flex gap-1 -mb-px border-b">
          {(["list", "search"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "px-3 py-1.5 text-sm border-b-2 transition-colors",
                mode === m
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {m === "list" ? "列表" : "語義搜尋"}
            </button>
          ))}
        </div>
      </div>

      {!tenantId ? (
        <p className="text-muted-foreground text-sm py-6 text-center">
          請輸入 Tenant ID
        </p>
      ) : mode === "list" ? (
        <>
          {isLoading && <p className="text-muted-foreground">載入中...</p>}
          {error && (
            <p className="text-destructive">
              載入失敗：{(error as Error).message}
            </p>
          )}
          {!isLoading && data && <ConvSummaryList items={data.items} />}
        </>
      ) : (
        <ConvSummarySearchPanel tenantId={tenantId} botId={botId} />
      )}
    </div>
  );
}
