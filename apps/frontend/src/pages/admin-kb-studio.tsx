import { useParams } from "react-router-dom";
import { Suspense, lazy } from "react";
import {
  KbStudioTabs,
  useKbStudioTab,
} from "@/features/admin/kb-studio/kb-studio-tabs";
import { OverviewTab } from "@/features/admin/kb-studio/overview-tab";
import { DocumentsTab } from "@/features/admin/kb-studio/documents-tab";
import { SettingsTab } from "@/features/admin/kb-studio/settings-tab";
import { QualityTab } from "@/features/admin/kb-studio/quality-tab";

const ChunksTab = lazy(() =>
  import("@/features/admin/kb-studio/chunks-tab").then((m) => ({
    default: m.ChunksTab,
  })),
);
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

export default function AdminKbStudioPage() {
  const { kbId = "" } = useParams<{ kbId: string }>();
  const [activeTab, setActiveTab] = useKbStudioTab();

  return (
    <div className="flex flex-col h-full gap-4">
      <header>
        <div className="text-xs text-muted-foreground font-mono">{kbId}</div>
        <h1 className="text-2xl font-bold">KB Studio</h1>
        <p className="text-sm text-muted-foreground">
          chunk 編輯 / 分類管理 / 檢索測試 / 品質統計，一站式 RAG 調優工作室
        </p>
      </header>
      <KbStudioTabs active={activeTab} onChange={setActiveTab} />

      <div className="flex-1 min-h-0">
        <Suspense
          fallback={
            <p className="text-muted-foreground">載入 tab...</p>
          }
        >
          {activeTab === "overview" && <OverviewTab kbId={kbId} />}
          {activeTab === "documents" && <DocumentsTab kbId={kbId} />}
          {activeTab === "chunks" && <ChunksTab kbId={kbId} />}
          {activeTab === "categories" && <CategoriesTab kbId={kbId} />}
          {activeTab === "playground" && (
            <RetrievalPlaygroundTab kbId={kbId} />
          )}
          {activeTab === "quality" && <QualityTab kbId={kbId} />}
          {activeTab === "settings" && <SettingsTab kbId={kbId} />}
        </Suspense>
      </div>
    </div>
  );
}
