import { useParams } from "react-router-dom";
import { Suspense, lazy } from "react";
import {
  KbStudioTabs,
  useKbStudioTab,
} from "@/features/admin/kb-studio/kb-studio-tabs";
import { DocumentsTab } from "@/features/admin/kb-studio/documents-tab";
import { SettingsTab } from "@/features/admin/kb-studio/settings-tab";
import { QualityTab } from "@/features/admin/kb-studio/quality-tab";
import { useDocuments } from "@/hooks/queries/use-documents";

// 大型 tab lazy load（Categories 拖拉互動 / Playground 檢索 — 都不是進頁第一個看到的）
const CategoriesTab = lazy(() =>
  import("@/features/admin/kb-studio/categories-tab").then((m) => ({
    default: m.CategoriesTab,
  })),
);
const RetrievalPlaygroundTab = lazy(() =>
  import("@/features/admin/kb-studio/retrieval-playground-tab").then((m) => ({
    default: m.RetrievalPlaygroundTab,
  })),
);

interface StatProps {
  label: string;
  value: number;
  accent?: "ok" | "warn";
}

function StatCard({ label, value, accent = "ok" }: StatProps) {
  return (
    <div className="rounded-md border bg-card px-3 py-2 min-w-[5rem]">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={
          accent === "warn"
            ? "text-xl font-bold text-amber-600"
            : "text-xl font-bold"
        }
      >
        {value}
      </div>
    </div>
  );
}

function HeaderStats({ kbId }: { kbId: string }) {
  const { data: pagedData } = useDocuments(kbId);
  const documents = pagedData?.items ?? [];
  const failedCount = documents.filter((d) => d.status === "failed").length;
  return (
    <div className="flex flex-wrap gap-2">
      <StatCard label="文件數" value={documents.length} />
      <StatCard
        label="處理中"
        value={
          documents.filter(
            (d) => d.status === "pending" || d.status === "processing",
          ).length
        }
      />
      <StatCard
        label="失敗"
        value={failedCount}
        accent={failedCount > 0 ? "warn" : "ok"}
      />
    </div>
  );
}

export default function AdminKbStudioPage() {
  const { kbId = "" } = useParams<{ kbId: string }>();
  const [activeTab, setActiveTab] = useKbStudioTab();

  return (
    <div className="flex flex-col h-full gap-4">
      <header className="space-y-2">
        <div className="text-xs text-muted-foreground font-mono">{kbId}</div>
        <h1 className="text-2xl font-bold">KB Studio</h1>
        <p className="text-sm text-muted-foreground">
          chunk 編輯（直接點文件查看分塊就能改）/ 分類管理 / 檢索測試 /
          品質統計 — RAG 調優工作室
        </p>
        <HeaderStats kbId={kbId} />
      </header>
      <KbStudioTabs active={activeTab} onChange={setActiveTab} />

      <div className="flex-1 min-h-0">
        <Suspense
          fallback={<p className="text-muted-foreground">載入 tab...</p>}
        >
          {activeTab === "documents" && <DocumentsTab kbId={kbId} />}
          {activeTab === "categories" && <CategoriesTab kbId={kbId} />}
          {activeTab === "playground" && (
            <RetrievalPlaygroundTab kbId={kbId} />
          )}
          {activeTab === "quality" && (
            <QualityTab
              kbId={kbId}
              onEditChunk={() => setActiveTab("documents")}
            />
          )}
          {activeTab === "settings" && <SettingsTab kbId={kbId} />}
        </Suspense>
      </div>
    </div>
  );
}
