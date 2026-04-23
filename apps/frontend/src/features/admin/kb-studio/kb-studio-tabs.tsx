import { useSearchParams } from "react-router-dom";
import { cn } from "@/lib/utils";

export type KbStudioTab =
  | "overview"
  | "documents"
  | "chunks"
  | "categories"
  | "playground"
  | "quality"
  | "settings";

interface TabDef {
  key: KbStudioTab;
  label: string;
}

const TABS: TabDef[] = [
  { key: "overview", label: "概覽" },
  { key: "documents", label: "文件" },
  { key: "chunks", label: "Chunks" },
  { key: "categories", label: "分類" },
  { key: "playground", label: "Retrieval Playground" },
  { key: "quality", label: "品質" },
  { key: "settings", label: "設定" },
];

export function useKbStudioTab(): [KbStudioTab, (tab: KbStudioTab) => void] {
  const [params, setParams] = useSearchParams();
  const current = (params.get("tab") as KbStudioTab) || "overview";
  const setTab = (tab: KbStudioTab) => {
    params.set("tab", tab);
    setParams(params);
  };
  return [current, setTab];
}

interface TabsProps {
  active: KbStudioTab;
  onChange: (tab: KbStudioTab) => void;
}

export function KbStudioTabs({ active, onChange }: TabsProps) {
  return (
    <div className="border-b">
      <nav className="flex gap-1 -mb-px overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={cn(
              "px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors",
              active === t.key
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
