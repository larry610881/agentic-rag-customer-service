import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import { Activity, Search } from "lucide-react";
import { ConversationListPanel } from "@/features/admin/conversation-insights/conversation-list-panel";
import { ConversationDetailPanel } from "@/features/admin/conversation-insights/conversation-detail-panel";
import {
  AgentTracesFilterRow,
  daysToDateFrom,
  useAgentTracesFilterUrl,
} from "@/features/admin/components/agent-traces-filter-row";
import { AgentTracesGroupedTable } from "@/features/admin/components/agent-traces-grouped-table";
import { AgentTracesTable } from "@/features/admin/components/agent-traces-table";
import { ObservabilityEvalsTable } from "@/features/admin/components/observability-evals-table";
import type { AgentTraceFilters } from "@/hooks/queries/use-agent-traces";

const VALID_TABS = ["messages", "trace", "summary", "token"] as const;
type DetailTab = (typeof VALID_TABS)[number];

type PageTab = "conv-insights" | "evals";
type BrowseMode = "browse" | "search";

export default function AdminConversationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const cid = searchParams.get("cid");
  const rawTab = searchParams.get("tab") ?? "messages";
  const detailTab = (VALID_TABS as readonly string[]).includes(rawTab)
    ? (rawTab as DetailTab)
    : "messages";

  const [pageTab, setPageTab] = useState<PageTab>("conv-insights");
  const [browseMode, setBrowseMode] = useState<BrowseMode>("browse");
  const [summaryFromList, setSummaryFromList] = useState<string | null>(null);

  // 原可觀測性 filter row state
  const [filterValue, setFilterValue] = useAgentTracesFilterUrl();
  const apiFilters: Omit<AgentTraceFilters, "limit" | "offset"> = useMemo(
    () => ({
      tenant_id: filterValue.tenant_id,
      bot_id: filterValue.bot_id,
      source: filterValue.source,
      agent_mode: filterValue.agent_mode,
      outcome: filterValue.outcome,
      min_total_ms: filterValue.min_total_ms,
      max_total_ms: filterValue.max_total_ms,
      min_total_tokens: filterValue.min_total_tokens,
      max_total_tokens: filterValue.max_total_tokens,
      keyword: filterValue.keyword,
      date_from: daysToDateFrom(filterValue.days),
    }),
    [filterValue],
  );

  const handleSelectConv = useCallback(
    (conversationId: string, summary?: string | null) => {
      setSummaryFromList(summary ?? null);
      setSearchParams(
        { cid: conversationId, tab: "messages" },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  const handleTabChange = useCallback(
    (next: string) => {
      if (!cid) return;
      setSearchParams({ cid, tab: next }, { replace: true });
    },
    [cid, setSearchParams],
  );

  return (
    <div className="flex flex-col gap-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">對話與追蹤</h1>
        <p className="text-muted-foreground text-sm">
          瀏覽最近 agent traces、搜尋對話、看 trace / 摘要 / token 用量一次到位
        </p>
      </header>

      <Tabs value={pageTab} onValueChange={(v) => setPageTab(v as PageTab)}>
        <TabsList>
          <TabsTrigger value="conv-insights">對話追蹤</TabsTrigger>
          <TabsTrigger value="evals">品質評估</TabsTrigger>
        </TabsList>

        <TabsContent value="conv-insights" className="mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(380px,480px)_1fr] gap-4 min-h-[calc(100vh-260px)]">
            <aside className="flex flex-col gap-3 rounded-md border bg-card p-3 overflow-hidden">
              <ToggleGroup
                type="single"
                value={browseMode}
                onValueChange={(v) => {
                  if (v === "browse" || v === "search") setBrowseMode(v);
                }}
                className="w-fit border rounded-md"
              >
                <ToggleGroupItem value="browse" className="px-3 text-sm">
                  <Activity className="mr-1.5 h-3.5 w-3.5" />
                  瀏覽最近
                </ToggleGroupItem>
                <ToggleGroupItem value="search" className="px-3 text-sm">
                  <Search className="mr-1.5 h-3.5 w-3.5" />
                  搜尋對話
                </ToggleGroupItem>
              </ToggleGroup>

              {browseMode === "browse" ? (
                <div className="flex flex-col gap-3 overflow-hidden">
                  <AgentTracesFilterRow
                    value={filterValue}
                    onChange={setFilterValue}
                  />
                  <div className="overflow-auto">
                    {filterValue.view === "grouped" ? (
                      <AgentTracesGroupedTable
                        filters={apiFilters}
                        onSelectTrace={() => {
                          /* flat trace row clicks open detail — 本頁不用，交給右側 Trace tab */
                        }}
                        onSelectConversation={(conversationId) =>
                          handleSelectConv(conversationId, null)
                        }
                        selectedConversationId={cid}
                      />
                    ) : (
                      <AgentTracesTable
                        filters={apiFilters}
                        onSelectTrace={(t) =>
                          t.conversation_id &&
                          handleSelectConv(t.conversation_id, null)
                        }
                      />
                    )}
                  </div>
                </div>
              ) : (
                <ConversationListPanel
                  selectedConversationId={cid}
                  onSelect={handleSelectConv}
                />
              )}
            </aside>

            <main className="rounded-md border bg-card">
              {cid ? (
                <ConversationDetailPanel
                  conversationId={cid}
                  tab={detailTab}
                  onTabChange={handleTabChange}
                  summaryFromList={summaryFromList}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground p-8 text-center">
                  <div>
                    <p className="text-lg mb-2">從左側選一個對話開始</p>
                    <p className="text-sm">
                      瀏覽模式顯示最近 traces；搜尋模式用關鍵字或語意搜尋
                    </p>
                  </div>
                </div>
              )}
            </main>
          </div>
        </TabsContent>

        <TabsContent value="evals" className="mt-4">
          <ObservabilityEvalsTable />
        </TabsContent>
      </Tabs>
    </div>
  );
}
