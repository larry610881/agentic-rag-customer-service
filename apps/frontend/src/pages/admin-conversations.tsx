import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ConversationListPanel } from "@/features/admin/conversation-insights/conversation-list-panel";
import { ConversationDetailPanel } from "@/features/admin/conversation-insights/conversation-detail-panel";

const VALID_TABS = ["messages", "trace", "summary", "token"] as const;
type Tab = (typeof VALID_TABS)[number];

export default function AdminConversationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const cid = searchParams.get("cid");
  const rawTab = searchParams.get("tab") ?? "messages";
  const tab = (VALID_TABS as readonly string[]).includes(rawTab)
    ? (rawTab as Tab)
    : "messages";

  // list item 上的 summary，避免額外 API 呼叫就能顯示「摘要」tab 預覽
  const [summaryFromList, setSummaryFromList] = useState<string | null>(null);

  const handleSelect = useCallback(
    (conversationId: string, summary: string | null | undefined) => {
      setSummaryFromList(summary ?? null);
      // push 新 cid 進 history（允許 back 回列表狀態），tab 保持 default
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
      // 切 tab 用 replace，不污染 history
      setSearchParams({ cid, tab: next }, { replace: true });
    },
    [cid, setSearchParams],
  );

  return (
    <div className="flex flex-col gap-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">對話與追蹤</h1>
        <p className="text-muted-foreground text-sm">
          搜尋對話、看 agent trace、摘要與 token 用量一次到位
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(340px,420px)_1fr] gap-4 min-h-[calc(100vh-180px)]">
        <aside className="rounded-md border bg-card p-3">
          <ConversationListPanel
            selectedConversationId={cid}
            onSelect={handleSelect}
          />
        </aside>
        <main className="rounded-md border bg-card">
          {cid ? (
            <ConversationDetailPanel
              conversationId={cid}
              tab={tab}
              onTabChange={handleTabChange}
              summaryFromList={summaryFromList}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground p-8 text-center">
              <div>
                <p className="text-lg mb-2">從左側搜尋並選一個對話</p>
                <p className="text-sm">訊息、trace、摘要、token 用量會在這裡顯示</p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
