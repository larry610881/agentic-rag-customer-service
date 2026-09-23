import { useSearchParams } from "react-router-dom";

// Tab 7→5 重組（2026-04-29）：
// - 移除 overview（統計 cards 上提到 page header）
// - 移除 chunks（drill-down 編輯由「文件」tab 內「查看分塊」對話框承擔）
// - 默認 tab 改為 documents
export type KbStudioTab =
  | "documents"
  | "categories"
  | "playground"
  | "quality"
  | "settings";

interface TabDef {
  key: KbStudioTab;
  label: string;
}

export const KB_STUDIO_TABS: TabDef[] = [
  { key: "documents", label: "文件管理" },
  { key: "categories", label: "分類" },
  { key: "playground", label: "Retrieval Playground" },
  { key: "quality", label: "品質" },
  { key: "settings", label: "設定" },
];

const VALID_TABS = new Set<KbStudioTab>(KB_STUDIO_TABS.map((t) => t.key));

export function useKbStudioTab(): [KbStudioTab, (tab: KbStudioTab) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab") as KbStudioTab | null;
  // 舊網址 ?tab=overview / ?tab=chunks 自動 fallback 到 documents（含 deep link）
  const current: KbStudioTab =
    raw && VALID_TABS.has(raw) ? raw : "documents";
  const setTab = (tab: KbStudioTab) => {
    params.set("tab", tab);
    setParams(params);
  };
  return [current, setTab];
}
